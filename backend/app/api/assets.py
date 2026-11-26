"""Independent document library; writes append versions and never overwrite originals."""

import hashlib
from pathlib import Path
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile
from fastapi.responses import FileResponse
from pydantic import Field, StringConstraints
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..application.assets import (
    asset_detail,
    asset_for,
    asset_summaries,
    discard_uncommitted_file,
    duplicate_versions,
    next_version,
    original_path,
    revision_query,
    revision_view,
)
from ..application.subjects import subject_for
from ..application.workspaces import personal_workspace
from ..config import settings
from ..db import get_db, now, uid
from ..models import Asset, AssetRevision, Blob
from ..parsing import MIMES
from ..schemas import StrictModel
from .dependencies import current_user

router = APIRouter()


class AssetUpdate(StrictModel):
    revision: int = Field(ge=1)
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=250)]
    category: str = Field(default="", max_length=100)
    subject_id: str | None = Field(default=None, max_length=36)
    archived: bool = False


def expect_asset_revision(asset, revision):
    if asset.revision != revision:
        raise HTTPException(409, "资料已变化，请刷新后重试")


@router.get("/api/v1/assets")
def list_assets(
    q: str = Query("", max_length=100),
    category: str = Query("", max_length=100),
    subject_id: str | None = None,
    inbox: bool = False,
    include_archived: bool = False,
    limit: int = Query(40, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user=Depends(current_user),
    db: Session = Depends(get_db),
):
    workspace = personal_workspace(db, user.id)
    filters = [Asset.workspace_id == workspace.id]
    if not include_archived:
        filters.append(Asset.archived.is_(False))
    if inbox:
        filters.append(Asset.subject_id.is_(None))
    if subject_id:
        subject_for(db, workspace.id, subject_id)
        filters.append(Asset.subject_id == subject_id)
    if category:
        filters.append(Asset.category == category)
    if q.strip():
        filters.append(
            or_(
                Asset.title.contains(q.strip(), autoescape=True),
                Asset.category.contains(q.strip(), autoescape=True),
            )
        )
    total = db.scalar(select(func.count()).select_from(Asset).where(*filters))
    assets = db.scalars(
        select(Asset).where(*filters).order_by(Asset.updated_at.desc(), Asset.id).offset(offset).limit(limit)
    ).all()
    result = {"items": asset_summaries(db, assets), "total": total, "limit": limit, "offset": offset}
    db.commit()
    return result


@router.get("/api/v1/assets/{asset_id}")
def get_asset(asset_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    workspace = personal_workspace(db, user.id)
    return asset_detail(db, asset_for(db, workspace.id, asset_id))


@router.patch("/api/v1/assets/{asset_id}")
def edit_asset(asset_id: str, body: AssetUpdate, user=Depends(current_user), db: Session = Depends(get_db)):
    workspace = personal_workspace(db, user.id, True)
    asset = asset_for(db, workspace.id, asset_id, True)
    expect_asset_revision(asset, body.revision)
    if body.subject_id:
        subject = subject_for(db, workspace.id, body.subject_id)
        if subject.archived and asset.subject_id != subject.id:
            raise HTTPException(409, "主体已归档，请先恢复档案")
    values = body.model_dump(exclude={"revision"})
    values["category"] = values["category"].strip()
    if any(getattr(asset, key) != value for key, value in values.items()):
        for key, value in values.items():
            setattr(asset, key, value)
        asset.revision += 1
        asset.updated_at = now()
    db.commit()
    return asset_detail(db, asset)


async def save_upload(db, user, file, asset_id=None, revision=None):
    filename = Path((file.filename or "file").replace("\\", "/")).name[:250]
    suffix = Path(filename).suffix.lower()
    if suffix not in MIMES:
        raise HTTPException(415, "支持 PDF、DOCX、TXT、MD、PNG 和 JPEG")
    raw = await file.read(settings.max_file_bytes + 1)
    if not raw:
        raise HTTPException(422, "文件为空")
    if len(raw) > settings.max_file_bytes:
        raise HTTPException(413, "单文件不能超过 20 MiB")
    workspace = personal_workspace(db, user.id, True)
    if asset_id:
        asset = asset_for(db, workspace.id, asset_id, True)
        expect_asset_revision(asset, revision)
        if asset.archived:
            raise HTTPException(409, "资料已归档，请先恢复后再上传版本")
        asset.revision += 1
        asset.updated_at = now()
    else:
        asset = Asset(workspace_id=workspace.id, title=filename)
        db.add(asset)
        db.flush()
    digest = hashlib.sha256(raw).hexdigest()
    duplicates = duplicate_versions(db, workspace.id, digest, len(raw))
    key = uid() + suffix
    settings.storage.mkdir(parents=True, exist_ok=True)
    path = settings.storage / key
    try:
        path.write_bytes(raw)
        blob = Blob(
            workspace_id=workspace.id, storage_key=key, sha256=digest, size=len(raw), mime=MIMES[suffix]
        )
        db.add(blob)
        db.flush()
        version = AssetRevision(
            workspace_id=workspace.id,
            asset_id=asset.id,
            blob_id=blob.id,
            version=next_version(db, asset),
            filename=filename,
        )
        db.add(version)
        db.flush()
        db.commit()
    except Exception:
        discard_uncommitted_file(db, path)
        raise
    return {"asset": asset_detail(db, asset), "duplicates": duplicates}


@router.post("/api/v1/assets", status_code=201)
async def upload_asset(
    file: UploadFile = File(...), user=Depends(current_user), db: Session = Depends(get_db)
):
    return await save_upload(db, user, file)


@router.post("/api/v1/assets/{asset_id}/versions", status_code=201)
async def upload_asset_version(
    asset_id: str,
    file: UploadFile = File(...),
    revision: int = Form(..., ge=1),
    user=Depends(current_user),
    db: Session = Depends(get_db),
):
    return await save_upload(db, user, file, asset_id, revision)


def version_for(db, user, revision_id):
    workspace = personal_workspace(db, user.id)
    row = db.execute(
        revision_query().where(AssetRevision.id == revision_id, AssetRevision.workspace_id == workspace.id)
    ).first()
    if not row:
        raise HTTPException(404, "资料版本不存在")
    return row


@router.get("/api/v1/asset-revisions/{revision_id}")
def get_asset_version(revision_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    revision, blob, has_text, has_inline = version_for(db, user, revision_id)
    return revision_view(revision, blob, True, has_text=has_text, has_inline=has_inline)


@router.get("/api/v1/asset-revisions/{revision_id}/content")
def get_asset_content(revision_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    revision, blob, _, has_inline = version_for(db, user, revision_id)
    if has_inline:
        return Response(
            blob.inline_content,
            media_type=blob.mime,
            headers={"Content-Disposition": "attachment; filename*=UTF-8''" + quote(revision.filename)},
        )
    path = original_path(blob.storage_key)
    if not path or not path.is_file():
        raise HTTPException(404, "原件暂不可用；已有文本快照仍可查看")
    return FileResponse(
        path,
        media_type=blob.mime,
        filename=revision.filename,
        content_disposition_type="inline"
        if blob.mime in {"application/pdf", "image/png", "image/jpeg"}
        else "attachment",
    )
