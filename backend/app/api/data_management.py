from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..application.assets import asset_for, original_path
from ..application.backup import LIMIT, export_backup, read_backup, restore_backup
from ..application.workspaces import personal_workspace
from ..db import get_db
from ..models import AssetRevision, Blob, Case, Document, MaterialPacket
from ..schemas import RevisionInput
from .dependencies import current_user

router = APIRouter()


@router.get("/api/v1/data/backup")
def backup(user=Depends(current_user), db: Session = Depends(get_db)):
    return Response(
        export_backup(db, user),
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="packetpilot-data-backup.zip"'},
    )


@router.post("/api/v1/data/restore-preview")
async def preview(file: UploadFile = File(...), user=Depends(current_user)):
    raw = await file.read(LIMIT + 1)
    if len(raw) > LIMIT:
        raise HTTPException(413, "备份文件过大")
    data, contents = read_backup(raw)
    return {
        "cases": len(data["tables"]["cases"]),
        "documents": len(data["tables"]["document_versions"]),
        "files": len(contents) - 1,
        "notice": "恢复将创建独立副本；不会覆盖当前事项，不恢复密码、会话与外部授权",
    }


@router.post("/api/v1/data/restore")
async def restore(file: UploadFile = File(...), user=Depends(current_user), db: Session = Depends(get_db)):
    raw = await file.read(LIMIT + 1)
    if len(raw) > LIMIT:
        raise HTTPException(413, "备份文件过大")
    try:
        return restore_backup(db, user, raw)
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(422, "备份关联校验失败，已回滚导入") from error


@router.delete("/api/v1/assets/{asset_id}/purge")
def purge(asset_id: str, body: RevisionInput, user=Depends(current_user), db: Session = Depends(get_db)):
    space = personal_workspace(db, user.id, True)
    asset = asset_for(db, space.id, asset_id, True)
    if asset.revision != body.revision or not asset.archived:
        raise HTTPException(409, "先归档并确认最新资料版本")
    revisions = list(db.scalars(select(AssetRevision).where(AssetRevision.asset_id == asset.id)))
    ids = {r.id for r in revisions}
    if db.scalar(select(Document.id).where(Document.asset_revision_id.in_(ids)).limit(1)):
        raise HTTPException(409, "资料仍被事项或历史版本引用，请先移除相关事项引用")
    for packet in db.scalars(
        select(MaterialPacket)
        .join(Case, Case.id == MaterialPacket.case_id)
        .where(Case.workspace_id == space.id)
    ):
        if any(e.get("asset_revision_id") in ids for e in packet.manifest.get("entries", [])):
            raise HTTPException(409, "冻结材料包仍保留此版本；需先处理相关事项与交付保留需求")
    blob_ids = {r.blob_id for r in revisions}
    db.delete(asset)
    db.flush()
    paths = []
    for identifier in blob_ids:
        if not db.scalar(select(AssetRevision.id).where(AssetRevision.blob_id == identifier).limit(1)):
            blob = db.get(Blob, identifier)
            if blob and blob.workspace_id == space.id:
                if blob.storage_key:
                    path = original_path(blob.storage_key)
                    if path:
                        paths.append(path)
                db.delete(blob)
    db.commit()
    for path in paths:
        path.unlink(missing_ok=True)
    return {"ok": True, "notice": "当前资料及无引用原件已清除；此前导出的备份、下载包和外部副本需另行删除"}
