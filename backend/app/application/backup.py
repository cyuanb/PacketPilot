"""Owner-scoped portable backups; restores append copies and never overwrite current data."""

import base64
import hashlib
import io
import json
import zipfile
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select

from .. import models
from ..config import settings
from ..db import uid
from .assets import original_path
from .workspaces import personal_workspace

TABLES = [
    models.SubjectProfile,
    models.Asset,
    models.Blob,
    models.AssetRevision,
    models.Case,
    models.CaseSubjectRole,
    models.Document,
    models.CaseDocumentLink,
    models.RuleSet,
    models.ParseRevision,
    models.Run,
    models.Message,
    models.RunEvent,
    models.ToolCall,
    models.Attestation,
    models.Audit,
    models.Issue,
    models.IssueEvent,
    models.MaterialPacket,
    models.DeliveryRecord,
    models.WorkItem,
    models.WorkEvent,
]
LIMIT = 300 * 1024 * 1024


def export_backup(db, user):
    workspace = personal_workspace(db, user.id)
    cases = set(db.scalars(select(models.Case.id).where(models.Case.workspace_id == workspace.id)))
    selected = {}
    ids = {}
    links = {
        "document_id": "document_versions",
        "run_id": "runs",
        "issue_id": "issues",
        "packet_id": "material_packets",
        "item_id": "work_items",
    }
    for model in TABLES:
        table = model.__table__
        query = select(model)
        if "workspace_id" in table.c:
            query = query.where(table.c.workspace_id == workspace.id)
        elif "case_id" in table.c:
            query = query.where(table.c.case_id.in_(cases))
        else:
            key = next(k for k in links if k in table.c)
            query = query.where(table.c[key].in_(ids.get(links[key], set())))
        rows = []
        for obj in db.scalars(query):
            row = {}
            for column in table.c:
                value = getattr(obj, column.name)
                if isinstance(value, bytes):
                    value = {"$bytes": base64.b64encode(value).decode()}
                elif isinstance(value, datetime):
                    value = value.isoformat()
                row[column.name] = value
            rows.append(row)
        selected[table.name] = rows
        ids[table.name] = {r["id"] for r in rows if "id" in r}
    files = {}
    for table in ("blobs", "document_versions"):
        for row in selected[table]:
            key = row.get("storage_key")
            if key and key not in files:
                path = original_path(key)
                if not path or not path.is_file():
                    raise HTTPException(409, "存在缺失原件，无法制作完整备份")
                files[key] = path.read_bytes()
    payload = {
        "schema": "packetpilot.backup/1",
        "workspace_id": workspace.id,
        "owner_id": user.id,
        "tables": selected,
    }
    data = json.dumps(payload, ensure_ascii=False).encode()
    if len(data) + sum(map(len, files.values())) > LIMIT:
        raise HTTPException(413, "便携备份超过 300 MiB，请使用原生管理备份")
    manifest = {
        name: hashlib.sha256(raw).hexdigest()
        for name, raw in {"data.json": data, **{"files/" + k: v for k, v in files.items()}}.items()
    }
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("data.json", data)
        for key, raw in files.items():
            z.writestr("files/" + key, raw)
        z.writestr("checksums.json", json.dumps(manifest))
    return output.getvalue()


def read_backup(raw):
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            names = z.namelist()
            if (
                len(names) != len(set(names))
                or len(names) > 10000
                or sum(i.file_size for i in z.infolist()) > LIMIT
            ):
                raise ValueError("备份大小或条目数量无效")
            manifest = json.loads(z.read("checksums.json"))
            if set(names) != {*manifest, "checksums.json"}:
                raise ValueError("备份文件清单不一致")
            contents = {name: z.read(name) for name in manifest}
            if any(hashlib.sha256(contents[n]).hexdigest() != h for n, h in manifest.items()):
                raise ValueError("备份哈希不一致")
            data = json.loads(contents["data.json"])
            if data["schema"] != "packetpilot.backup/1" or set(data["tables"]) != {
                m.__tablename__ for m in TABLES
            }:
                raise ValueError("不支持的备份版本或数据表")
            for model in TABLES:
                if any(
                    set(row) != {c.name for c in model.__table__.c}
                    for row in data["tables"][model.__tablename__]
                ):
                    raise ValueError("备份字段与当前版本不一致")
            return data, contents
    except (ValueError, KeyError, zipfile.BadZipFile) as error:
        raise HTTPException(422, "备份无效：" + str(error)[:100]) from error


def restore_backup(db, user, raw):
    from sqlalchemy import DateTime, Integer

    data, contents = read_backup(raw)
    for blob in data["tables"]["blobs"]:
        if blob.get("storage_key"):
            value = contents.get("files/" + blob["storage_key"])
        elif blob.get("inline_content"):
            value = base64.b64decode(blob["inline_content"]["$bytes"], validate=True)
        else:
            value = None
        if value is None or len(value) != blob["size"] or hashlib.sha256(value).hexdigest() != blob["sha256"]:
            raise HTTPException(422, "备份原件内容与资料元数据不一致")
    for document in data["tables"]["document_versions"]:
        if document.get("storage_key") and "files/" + document["storage_key"] not in contents:
            raise HTTPException(422, "备份缺少文档原件，拒绝引用现有磁盘文件")
    space = personal_workspace(db, user.id, True)
    mapping = {data["owner_id"]: user.id, data["workspace_id"]: space.id}
    for model in TABLES:
        for row in data["tables"][model.__tablename__]:
            if isinstance(row.get("id"), str):
                mapping[row["id"]] = uid()
            for key, value in row.items():
                if key.endswith("_id") and isinstance(value, str) and value and value not in mapping:
                    mapping[value] = uid()
    mapping[data["owner_id"]] = user.id
    mapping[data["workspace_id"]] = space.id
    files = []
    for name, content in contents.items():
        if not name.startswith("files/"):
            continue
        key = name[6:]
        if "/" in key or "\\" in key or key in (".", ".."):
            raise HTTPException(422, "无效文件路径")
        suffix = __import__("pathlib").Path(key).suffix
        if suffix not in (".pdf", ".png", ".jpg", ".jpeg", ".txt", ".md", ".docx"):
            raise HTTPException(422, "无效原件类型")
        mapping[key] = uid() + suffix
        files.append((settings.storage / mapping[key], content))

    def remap(value):
        if isinstance(value, str):
            return mapping.get(value, value)
        if isinstance(value, list):
            return [remap(v) for v in value]
        if isinstance(value, dict):
            if set(value) == {"$bytes"}:
                return base64.b64decode(value["$bytes"], validate=True)
            return {mapping.get(k, k): remap(v) for k, v in value.items()}
        return value

    written = []
    try:
        for path, content in files:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
            written.append(path)
        for model in TABLES:
            for source in data["tables"][model.__tablename__]:
                row = remap(source)
                for key in ("owner_id", "actor_id"):
                    if key in row:
                        row[key] = user.id
                if "workspace_id" in row:
                    row["workspace_id"] = space.id
                for column in model.__table__.c:
                    if column.primary_key and isinstance(column.type, Integer):
                        row.pop(column.name, None)
                    elif isinstance(column.type, DateTime) and row[column.name]:
                        row[column.name] = datetime.fromisoformat(row[column.name])
                if model is models.MaterialPacket:
                    row["manifest"] = source[
                        "manifest"
                    ]  # Preserve the exact frozen archive's original manifest.
                if model is models.Run and row["status"] in ("queued", "running"):
                    row.update(
                        status="cancelled",
                        cancel_requested=True,
                        lease_until=None,
                        error="从备份恢复；原进行中任务未自动重放",
                    )
                db.add(model(**row))
            db.flush()
        db.commit()
    except Exception:
        db.rollback()
        # Only freshly generated files from this failed transaction are removed.
        for path in written:
            path.unlink(missing_ok=True)
        raise
    return {
        "cases_imported": len(data["tables"]["cases"]),
        "files_restored": len(files),
        "notice": "已作为独立副本导入；旧事项不覆盖，授权/密码/会话不恢复，冻结包保留原始清单",
    }
