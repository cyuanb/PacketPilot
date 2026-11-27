"""Case-local material copies pin library revisions and never follow latest implicitly."""

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import load_only

from ..models import Asset, AssetRevision, Blob, CaseDocumentLink, Document
from .assets import blob_available
from .cases import bump
from .runs import enqueue


def ensure_link(db, case, document):
    if document.asset_revision_id and not db.get(CaseDocumentLink, document.id):
        db.flush()
        db.add(
            CaseDocumentLink(
                document_id=document.id,
                case_id=case.id,
                workspace_id=case.workspace_id,
                asset_revision_id=document.asset_revision_id,
            )
        )


def linked_documents(db, case):
    latest = (
        select(AssetRevision.asset_id, func.max(AssetRevision.version).label("version"))
        .group_by(AssetRevision.asset_id)
        .subquery()
    )
    rows = db.execute(
        select(Document, Asset, AssetRevision, latest.c.version)
        .options(
            load_only(Document.id, Document.purpose, Document.category, Document.parse_status),
            load_only(Asset.id, Asset.title, Asset.archived),
            load_only(AssetRevision.id, AssetRevision.version),
        )
        .join(CaseDocumentLink, CaseDocumentLink.document_id == Document.id)
        .join(AssetRevision, AssetRevision.id == CaseDocumentLink.asset_revision_id)
        .join(Asset, Asset.id == AssetRevision.asset_id)
        .join(latest, latest.c.asset_id == Asset.id)
        .where(
            Document.case_id == case.id, Document.active, CaseDocumentLink.workspace_id == case.workspace_id
        )
        .order_by(Document.created_at)
    )
    return [
        {
            "document_id": document.id,
            "asset_id": asset.id,
            "asset_title": asset.title,
            "asset_revision_id": version.id,
            "version": version.version,
            "latest_version": newest,
            "update_available": newest > version.version,
            "archived": asset.archived,
            "purpose": document.purpose,
            "category": document.category,
            "parse_status": document.parse_status,
        }
        for document, asset, version, newest in rows
    ]


def bind_revision(db, case, revision_id, purpose, category, previous=None):
    row = db.execute(
        select(AssetRevision, Asset, Blob)
        .join(Asset, Asset.id == AssetRevision.asset_id)
        .join(Blob, Blob.id == AssetRevision.blob_id)
        .where(AssetRevision.id == revision_id, AssetRevision.workspace_id == case.workspace_id)
    ).first()
    if not row:
        raise HTTPException(404, "资料版本不存在")
    version, asset, blob = row
    if asset.archived:
        raise HTTPException(409, "资料已归档，请先恢复")
    if not blob_available(blob):
        raise HTTPException(409, "该版本原件不可用，不能加入事项")
    if previous:
        old_version = (
            db.get(AssetRevision, previous.asset_revision_id) if previous.asset_revision_id else None
        )
        if not previous.active or not old_version or old_version.asset_id != asset.id:
            raise HTTPException(409, "只能为当前材料选择同一资料的版本")
        if old_version.id == version.id:
            raise HTTPException(409, "已经使用这个版本")
    elif db.scalar(
        select(Document.id)
        .join(AssetRevision, AssetRevision.id == Document.asset_revision_id)
        .where(
            Document.case_id == case.id,
            Document.active,
            Document.purpose == purpose,
            AssetRevision.asset_id == asset.id,
        )
        .limit(1)
    ):
        raise HTTPException(409, "此资料已在该用途下关联，请在现有材料中选择版本")
    if (
        not previous
        and db.scalar(
            select(func.count()).select_from(Document).where(Document.case_id == case.id, Document.active)
        )
        >= 30
    ):
        raise HTTPException(422, "每事项最多 30 份材料")
    document = Document(
        case_id=case.id,
        asset_revision_id=version.id,
        title=asset.title,
        purpose=previous.purpose if previous else purpose,
        category=previous.category if previous else category or asset.category,
        filename=version.filename,
        storage_key=blob.storage_key or "",
        sha256=blob.sha256,
        size=blob.size,
        mime=blob.mime,
    )
    if previous:
        previous.active = False
        document.logical_id, document.version = previous.logical_id, previous.version + 1
    if version.origin == "correction" and version.text_snapshot:
        document.pages = version.text_snapshot
        document.parse_status, document.parse_method = "ready", "user_corrected"
        document.parse_note = "固定引用的校订文本；原件保留，应结合原件复核。"
    elif blob.inline_content is not None:
        document.pages = [{"number": 1, "label": "全文", "text": blob.inline_content.decode("utf-8")}]
        document.parse_status, document.parse_method = "ready", "library_text"
    db.add(document)
    bump(
        db,
        case,
        "material.version_selected" if previous else "material.linked",
        {"asset_id": asset.id, "asset_revision_id": version.id},
    )
    db.flush()
    ensure_link(db, case, document)
    from .parses import ensure_parse

    ensure_parse(db, document)
    if document.parse_status == "queued":
        enqueue(db, case, "parse", {"document_id": document.id})
    return document
