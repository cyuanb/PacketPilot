"""Frozen material archives. Downloads and delivery acknowledgements are separate acts."""

import hashlib
import io
import json
import re
import zipfile
from pathlib import PurePosixPath

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import defer

from ..db import now, uid
from ..models import AssetRevision, Blob, DeliveryRecord, MaterialPacket
from .assets import original_path
from .documents import documents_for
from .material_review import material_review
from .reports import checklist

MAX_PACKET_BYTES = 200 * 1024 * 1024


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def packet_inputs(db, case):
    return {
        "revision": case.revision,
        "rules_id": case.active_rules_id,
        "scenario": case.scenario_snapshot,
        "documents": [
            {
                "id": d.id,
                "logical_id": d.logical_id,
                "asset_revision_id": d.asset_revision_id,
                "parse_revision_id": d.current_parse_id,
                "sha256": d.sha256,
                "assignment": d.assignment,
            }
            for d in documents_for(db, case.id)
        ],
    }


def safe_entry_name(value):
    parts = value.replace("\\", "/").split("/")
    if (
        len(value) > 200
        or len(parts) > 4
        or any(
            not p
            or p in (".", "..")
            or p.endswith((".", " "))
            or re.search(r'[<>:"|?*\x00-\x1f]', p)
            or re.fullmatch(r"(?i)(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?", p)
            for p in parts
        )
    ):
        raise HTTPException(422, "包内文件名无效；使用相对目录，不能包含系统保留名或路径跳转")
    if parts[0].casefold() in ("manifest.json", "contents.txt"):
        raise HTTPException(422, "该名称保留给材料包目录和清单")
    return "/".join(parts)


def original_bytes(db, doc):
    rev = db.get(AssetRevision, doc.asset_revision_id) if doc.asset_revision_id else None
    blob = db.get(Blob, rev.blob_id) if rev else None
    if not blob:
        raise HTTPException(409, "原件版本不可用，请重新选择材料")
    if blob.size > MAX_PACKET_BYTES:
        raise HTTPException(413, "材料包超过 200 MiB 限制")
    if blob.inline_content is not None:
        raw = bytes(blob.inline_content)
    else:
        path = original_path(blob.storage_key)
        if not path or not path.is_file():
            raise HTTPException(409, "原件文件缺失，不能生成材料包")
        if path.stat().st_size != blob.size:
            raise HTTPException(409, "原件大小不一致，请恢复原件后重试")
        raw = path.read_bytes()
    if len(raw) != blob.size or hashlib.sha256(raw).hexdigest() != blob.sha256:
        raise HTTPException(409, "原件哈希校验失败，已阻止导出")
    return raw


def prepare_packet(db, case, body):
    docs = {
        d.id: d
        for d in documents_for(db, case.id)
        if d.purpose == "material" and (d.assignment or {}).get("state") != "rejected"
    }
    entries, contents, names, selected = [], [], set(), set()
    total = 0
    for entry in body.entries:
        d = docs.get(entry.document_id)
        if not d:
            raise HTTPException(409, "仅能选择当前事项有效的材料版本；通知和已移除材料不可入包")
        name = safe_entry_name(entry.path)
        if name.casefold() in names or d.id in selected:
            raise HTTPException(422, "文件路径或材料重复")
        names.add(name.casefold())
        selected.add(d.id)
        if entry.content == "original":
            raw = original_bytes(db, d)
            if PurePosixPath(name).suffix.lower() != PurePosixPath(d.filename).suffix.lower():
                raise HTTPException(422, "原件文件扩展名必须保持不变")
        else:
            if not name.endswith(".txt") or d.parse_status != "ready":
                raise HTTPException(422, "校订/解析文本需完整可读并使用 .txt 扩展名")
            raw = "\n\n".join(p["text"] for p in d.pages).encode("utf-8")
        total += len(raw)
        if total > MAX_PACKET_BYTES:
            raise HTTPException(413, "材料包超过 200 MiB 限制")
        entries.append(
            {
                "path": name,
                "document_id": d.id,
                "asset_revision_id": d.asset_revision_id,
                "document_version": d.version,
                "parse_revision_id": d.current_parse_id,
                "content": entry.content,
                "owner_review": material_review(d)["state"],
                "size": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
        contents.append((name, raw))
    report = checklist(db, case)
    warnings = []
    unconfirmed = sum(material_review(docs[e.document_id])["state"] != "confirmed" for e in body.entries)
    if unconfirmed:
        warnings.append(f"所选材料中有 {unconfirmed} 份尚未由本人确认当前版本；请先核对原件或明确接受此提示")
    if report["status"] != "ready" or not report["can_export"]:
        warnings.append("当前检查尚未就绪或已过时；此包不代表材料合格")
    if set(docs) - selected:
        warnings.append("部分当前材料未选择进入此包，请核对接收方清单")
    if any(docs[e.document_id].parse_status != "ready" for e in body.entries):
        warnings.append("所选原件含未完整读取材料，请人工核对")
    if any(e.content != "original" for e in body.entries):
        warnings.append("包含派生文本，它不保留原件版式、签名或印章")
    return entries, contents, warnings, report


def freeze_packet(db, case, body):
    request_digest = digest(body.model_dump(mode="json"))
    old = db.scalar(
        select(MaterialPacket).where(
            MaterialPacket.case_id == case.id, MaterialPacket.request_key == body.request_key
        )
    )
    if old:
        if old.request_digest != request_digest:
            raise HTTPException(409, "同一请求标识不可用于不同材料包")
        return old
    from .cases import expect_revision

    expect_revision(case, body.revision)
    entries, contents, warnings, report = prepare_packet(db, case, body)
    if warnings and not body.acknowledge_warnings:
        raise HTTPException(422, "请先预览并确认材料包中的未决提示")
    identifier = uid()
    manifest = {
        "schema": "packetpilot.material-packet/1",
        "packet_id": identifier,
        "title": body.title,
        "frozen_at": now().isoformat(),
        "scenario": (case.scenario_snapshot or {}).get("id"),
        "entries": entries,
        "warnings": warnings,
        "check_status": report["status"],
        "delivery_status": "not_recorded",
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, raw in contents:
            archive.writestr(name, raw)
        archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        archive.writestr(
            "contents.txt",
            body.title
            + "\n\n"
            + "\n".join(
                f"{i}. {e['path']} ({e['size']} bytes) SHA256 {e['sha256']}" for i, e in enumerate(entries, 1)
            )
            + "\n\n"
            + "\n".join(warnings),
        )
    raw = buffer.getvalue()
    packet = MaterialPacket(
        id=identifier,
        case_id=case.id,
        title=body.title,
        case_revision=case.revision,
        manifest=manifest,
        input_snapshot=packet_inputs(db, case),
        archive=raw,
        sha256=hashlib.sha256(raw).hexdigest(),
        request_key=body.request_key,
        request_digest=request_digest,
    )
    db.add(packet)
    db.flush()
    return packet


def packet_view(db, packet, case):
    current = packet_inputs(db, case)
    old = packet.input_snapshot
    old_docs = {d["id"]: d for d in old["documents"]}
    new_docs = {d["id"]: d for d in current["documents"]}
    events = list(
        db.scalars(
            select(DeliveryRecord)
            .where(DeliveryRecord.packet_id == packet.id)
            .order_by(DeliveryRecord.created_at, DeliveryRecord.id)
        )
    )
    return {
        "id": packet.id,
        "title": packet.title,
        "sha256": packet.sha256,
        "case_revision": packet.case_revision,
        "created_at": packet.created_at.isoformat(),
        "manifest": packet.manifest,
        "changed": old != current,
        "diff": {
            "added": sorted(new_docs.keys() - old_docs.keys()),
            "removed": sorted(old_docs.keys() - new_docs.keys()),
            "changed": sorted(k for k in old_docs.keys() & new_docs.keys() if old_docs[k] != new_docs[k]),
            "rules_changed": old["rules_id"] != current["rules_id"],
            "case_changed": old["revision"] != current["revision"],
        },
        "delivery_status": events[-1].status if events else "not_recorded",
        "deliveries": [
            {
                "id": e.id,
                "status": e.status,
                "channel": e.channel,
                "recipient": e.recipient,
                "reference": e.reference,
                "note": e.note,
                "occurred_at": e.occurred_at.isoformat(),
                "recorded_at": e.created_at.isoformat(),
            }
            for e in events
        ],
    }


def packets_for(db, case):
    return [
        packet_view(db, p, case)
        for p in db.scalars(
            select(MaterialPacket)
            .options(defer(MaterialPacket.archive))
            .where(MaterialPacket.case_id == case.id)
            .order_by(MaterialPacket.created_at.desc())
        )
    ]
