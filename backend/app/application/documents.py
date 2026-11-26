"""Document ownership queries and version projections."""

from fastapi import HTTPException
from sqlalchemy import select

from ..models import Document
from .cases import case_for


def doc_view(d, include_text=True):
    return {
        "id": d.id,
        "logical_id": d.logical_id,
        "version": d.version,
        "title": d.title,
        "purpose": d.purpose,
        "category": d.category,
        "filename": d.filename,
        "mime": d.mime,
        "size": d.size,
        "parse_status": d.parse_status,
        "parse_note": d.parse_note,
        "parse_method": d.parse_method,
        "active": d.active,
        "pages": d.pages if include_text else [],
        "page_count": len(d.pages),
        "created_at": d.created_at.isoformat(),
    }


def documents_for(db, case_id):
    return list(
        db.scalars(
            select(Document).where(Document.case_id == case_id, Document.active).order_by(Document.created_at)
        )
    )


def document_for(db, user, doc_id):
    d = db.get(Document, doc_id)
    if not d:
        raise HTTPException(404, "材料不存在")
    case_for(db, user.id, d.case_id)
    return d
