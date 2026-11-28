"""Document ownership queries and version projections."""

from fastapi import HTTPException
from sqlalchemy import select

from ..models import Document, RuleSet, Run
from .assets import remove_unretained_files
from .cases import bump, case_for
from .material_review import material_review


def doc_view(d, include_text=True):
    return {
        "id": d.id,
        "asset_revision_id": d.asset_revision_id,
        "parse_revision_id": d.current_parse_id,
        "assignment": {k: v for k, v in (d.assignment or {}).items() if k != "_confirmation"},
        "confirmation": material_review(d),
        "sha256": d.sha256,
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


def remove_case_material(db, user, doc_id):
    d = document_for(db, user, doc_id)
    c = case_for(db, user.id, d.case_id, True)
    versions = list(
        db.scalars(select(Document).where(Document.logical_id == d.logical_id, Document.case_id == c.id))
    )
    ids = {v.id for v in versions}
    keys = {v.storage_key for v in versions if v.storage_key}
    # Removing original evidence also removes affected historical check snapshots and message traces.
    runs = list(db.scalars(select(Run).where(Run.case_id == c.id)))
    for r in runs:
        if any(x["id"] in ids for x in r.snapshot.get("documents", [])):
            if c.current_check_id == r.id:
                c.current_check_id = None
            db.delete(r)
    for rules in db.scalars(select(RuleSet).where(RuleSet.case_id == c.id)):
        if ids.intersection(rules.source_ids):
            rules.status = "source_removed"
            if c.active_rules_id == rules.id:
                c.active_rules_id = None
    for v in versions:
        db.delete(v)
    bump(db, c, "document.deleted")
    db.commit()
    remove_unretained_files(db, keys)
    return {"ok": True}
