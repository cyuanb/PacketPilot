"""Append-only library content and compatibility capture for case-owned documents."""

import hashlib
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import defer, load_only

from ..config import settings
from ..db import now
from ..models import Asset, AssetRevision, Blob, Case, Document, SubjectProfile


def asset_for(db, workspace_id, asset_id, lock=False):
    query = select(Asset).where(Asset.id == asset_id, Asset.workspace_id == workspace_id)
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    asset = db.scalar(query)
    if not asset:
        raise HTTPException(404, "资料不存在")
    return asset


def original_path(key):
    if not key or key in {".", ".."} or "/" in key or "\\" in key or Path(key).is_absolute():
        return None
    path = (settings.storage / key).resolve()
    return path if path.is_relative_to(settings.storage) else None


def blob_available(blob, has_inline=None):
    path = original_path(blob.storage_key)
    if blob.storage_key:
        return path is not None and path.is_file()
    return has_inline if has_inline is not None else blob.inline_content is not None


def revision_query():
    return (
        select(
            AssetRevision,
            Blob,
            func.jsonb_array_length(AssetRevision.text_snapshot) > 0,
            Blob.inline_content.is_not(None),
        )
        .join(Blob, Blob.id == AssetRevision.blob_id)
        .options(defer(AssetRevision.text_snapshot), defer(Blob.inline_content))
    )


def revision_view(revision, blob, include_text=False, *, has_text=None, has_inline=None):
    result = {
        "id": revision.id,
        "asset_id": revision.asset_id,
        "version": revision.version,
        "filename": revision.filename,
        "sha256": blob.sha256,
        "size": blob.size,
        "mime": blob.mime,
        "origin": revision.origin,
        "available": blob_available(blob, has_inline),
        "created_at": revision.created_at.isoformat(),
        "has_text_snapshot": has_text if has_text is not None else bool(revision.text_snapshot),
    }
    if include_text:
        result["text_snapshot"] = revision.text_snapshot if result["has_text_snapshot"] else []
    return result


def asset_summaries(db, assets):
    ids = [asset.id for asset in assets]
    if not ids:
        return []
    latest = (
        select(AssetRevision.asset_id, func.max(AssetRevision.version).label("version"))
        .where(AssetRevision.asset_id.in_(ids))
        .group_by(AssetRevision.asset_id)
        .subquery()
    )
    versions = {
        revision.asset_id: revision_view(revision, blob, has_text=has_text, has_inline=has_inline)
        for revision, blob, has_text, has_inline in db.execute(
            revision_query().join(
                latest,
                (latest.c.asset_id == AssetRevision.asset_id) & (latest.c.version == AssetRevision.version),
            )
        )
    }
    subjects = {
        subject.id: subject
        for subject in db.scalars(
            select(SubjectProfile)
            .options(
                load_only(
                    SubjectProfile.id, SubjectProfile.name, SubjectProfile.label, SubjectProfile.archived
                )
            )
            .where(SubjectProfile.id.in_([asset.subject_id for asset in assets if asset.subject_id]))
        )
    }
    usages = dict(
        db.execute(
            select(AssetRevision.asset_id, func.count(func.distinct(Document.case_id)))
            .join(Document, Document.asset_revision_id == AssetRevision.id)
            .where(AssetRevision.asset_id.in_(ids))
            .group_by(AssetRevision.asset_id)
        ).all()
    )
    return [
        {
            "id": asset.id,
            "workspace_id": asset.workspace_id,
            "title": asset.title,
            "category": asset.category,
            "subject_id": asset.subject_id,
            "subject_name": subjects[asset.subject_id].name if asset.subject_id in subjects else None,
            "subject_label": subjects[asset.subject_id].label if asset.subject_id in subjects else None,
            "subject_archived": subjects[asset.subject_id].archived
            if asset.subject_id in subjects
            else False,
            "archived": asset.archived,
            "inbox": asset.subject_id is None,
            "revision": asset.revision,
            "latest": versions.get(asset.id),
            "case_count": usages.get(asset.id, 0),
            "created_at": asset.created_at.isoformat(),
            "updated_at": asset.updated_at.isoformat(),
        }
        for asset in assets
    ]


def asset_detail(db, asset):
    result = asset_summaries(db, [asset])[0]
    result["versions"] = [
        revision_view(revision, blob, has_text=has_text, has_inline=has_inline)
        for revision, blob, has_text, has_inline in db.execute(
            revision_query().where(AssetRevision.asset_id == asset.id).order_by(AssetRevision.version.desc())
        )
    ]
    result["usages"] = [
        {
            "case_id": case.id,
            "case_title": case.title,
            "document_id": document.id,
            "asset_revision_id": revision.id,
            "version": revision.version,
            "active": document.active,
            "purpose": document.purpose,
        }
        for document, case, revision in db.execute(
            select(Document, Case, AssetRevision)
            .options(
                load_only(Document.id, Document.active, Document.purpose),
                load_only(Case.id, Case.title),
                load_only(AssetRevision.id, AssetRevision.version),
            )
            .join(Case, Case.id == Document.case_id)
            .join(AssetRevision, AssetRevision.id == Document.asset_revision_id)
            .where(AssetRevision.asset_id == asset.id, Case.workspace_id == asset.workspace_id)
            .order_by(Case.updated_at.desc(), AssetRevision.version.desc())
        )
    ]
    return result


def duplicate_versions(db, workspace_id, digest, size):
    rows = db.execute(
        select(Asset, AssetRevision)
        .options(
            load_only(Asset.id, Asset.title, Asset.archived),
            load_only(AssetRevision.id, AssetRevision.version),
        )
        .join(AssetRevision, AssetRevision.asset_id == Asset.id)
        .join(Blob, Blob.id == AssetRevision.blob_id)
        .where(Asset.workspace_id == workspace_id, Blob.sha256 == digest, Blob.size == size)
        .order_by(AssetRevision.created_at.desc())
        .limit(20)
    )
    return [
        {
            "asset_id": asset.id,
            "title": asset.title,
            "revision_id": revision.id,
            "version": revision.version,
            "archived": asset.archived,
        }
        for asset, revision in rows
    ]


def next_version(db, asset):
    return (
        db.scalar(select(func.max(AssetRevision.version)).where(AssetRevision.asset_id == asset.id)) or 0
    ) + 1


def capture_document(db, case, document, previous=None):
    """Capture original bytes and any existing text without renumbering case documents."""
    db.flush()
    if document.asset_revision_id:
        return
    asset = db.scalar(
        select(Asset)
        .where(Asset.workspace_id == case.workspace_id, Asset.legacy_logical_id == document.logical_id)
        .with_for_update()
    )
    if not asset:
        asset = Asset(
            workspace_id=case.workspace_id,
            legacy_logical_id=document.logical_id,
            title=document.title,
            category=document.category,
        )
        db.add(asset)
        db.flush()
    else:
        asset.revision += 1
        asset.updated_at = now()
    blob = None
    if document.storage_key:
        blob = db.scalar(
            select(Blob).where(
                Blob.workspace_id == case.workspace_id, Blob.storage_key == document.storage_key
            )
        )
        if blob and (blob.sha256 != document.sha256 or blob.size != document.size):
            raise HTTPException(409, "原件记录不一致，不能覆盖已有资料版本")
    elif previous and document.parse_method == "user_corrected":
        if not previous.asset_revision_id:
            capture_document(db, case, previous)
        prior = db.get(AssetRevision, previous.asset_revision_id)
        blob = db.get(Blob, prior.blob_id)
    if blob is None:
        candidate = "\n\n".join(page["text"] for page in document.pages).encode()
        inline = (
            candidate
            if not document.storage_key
            and hashlib.sha256(candidate).hexdigest() == document.sha256
            and len(candidate) == document.size
            else None
        )
        blob = Blob(
            workspace_id=case.workspace_id,
            storage_key=document.storage_key or None,
            inline_content=inline,
            sha256=document.sha256,
            size=document.size,
            mime=document.mime,
        )
        db.add(blob)
        db.flush()
    revision = AssetRevision(
        id=document.id,
        workspace_id=case.workspace_id,
        asset_id=asset.id,
        blob_id=blob.id,
        version=next_version(db, asset),
        filename=document.filename,
        origin="correction" if document.parse_method == "user_corrected" else "case_upload",
        text_snapshot=document.pages if document.parse_method != "native" else [],
    )
    db.add(revision)
    db.flush()
    document.asset_revision_id = revision.id


def remove_unretained_files(db, keys):
    for key in set(filter(None, keys)):
        if db.scalar(select(Blob.id).where(Blob.storage_key == key).limit(1)):
            continue
        if db.scalar(select(Document.id).where(Document.storage_key == key).limit(1)):
            continue
        path = original_path(key)
        if path:
            path.unlink(missing_ok=True)


def discard_uncommitted_file(db, path):
    # A lost commit acknowledgement must not cause us to delete a committed original.
    try:
        db.rollback()
        persisted = db.scalar(select(Blob.id).where(Blob.storage_key == path.name).limit(1))
    except Exception:
        return  # Retain the file if the database cannot confirm whether it committed.
    if not persisted:
        path.unlink(missing_ok=True)
