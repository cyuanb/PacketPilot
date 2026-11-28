"""Append-only parse results; document pages remain a backwards-compatible projection."""

import re
from copy import deepcopy

from fastapi import HTTPException
from sqlalchemy import func, select

from ..models import Case, Document, ParseRevision, Run


def field_candidates(pages):
    fields = []
    for page in pages:
        for index, line in enumerate(page["text"].splitlines()):
            match = re.match(r"^\s*([^:：\n]{1,50})\s*[:：]\s*(.{1,300})\s*$", line)
            if match:
                region = next((r for r in page.get("regions", []) if r["text"].strip() == line.strip()), None)
                fields.append(
                    {
                        "id": f"{page['number']}:{index}",
                        "page": page["number"],
                        "label": match[1].strip(),
                        "value": match[2].strip(),
                        "quote": line,
                        "region_id": region["id"] if region else None,
                        "confirmed": False,
                    }
                )
    return fields[:1000]


def append_parse(db, doc, parsed, method="native", fields=None):
    version = (
        db.scalar(select(func.max(ParseRevision.version)).where(ParseRevision.document_id == doc.id)) or 0
    ) + 1
    item = ParseRevision(
        document_id=doc.id,
        version=version,
        parent_id=doc.current_parse_id,
        method=method,
        status=parsed["status"],
        pages=deepcopy(parsed["pages"]),
        fields=field_candidates(parsed["pages"]) if fields is None else fields,
        note=parsed.get("note", ""),
        engine=parsed.get("engine", "native"),
    )
    db.add(item)
    db.flush()
    doc.current_parse_id = item.id
    doc.pages, doc.parse_status, doc.parse_note, doc.parse_method = (
        item.pages,
        item.status,
        item.note,
        item.method,
    )
    return item


def ensure_parse(db, doc):
    if not doc.current_parse_id:
        db.flush()
        return append_parse(
            db,
            doc,
            {"pages": doc.pages, "status": doc.parse_status, "note": doc.parse_note},
            doc.parse_method,
        )
    return db.get(ParseRevision, doc.current_parse_id)


def schedule_reparse(db, case, doc):
    from .cases import bump
    from .runs import enqueue

    if not doc.active or not doc.storage_key:
        raise HTTPException(422, "仅当前文件原件可重新解析；粘贴文本可直接校订")
    pending = db.scalar(
        select(Run.id)
        .where(
            Run.case_id == case.id,
            Run.kind == "parse",
            Run.status.in_(["queued", "running"]),
            Run.payload["document_id"].astext == doc.id,
        )
        .limit(1)
    )
    if pending:
        raise HTTPException(409, "该材料已有解析任务，请等待完成或取消")
    ensure_parse(db, doc)
    doc.parse_status = "queued"
    bump(db, case, "document.reparse_requested", {"document_id": doc.id})
    return enqueue(db, case, "parse", {"document_id": doc.id})[0]


def mark_parse_cancelled(db, run):
    if run.kind != "parse":
        return
    case = db.scalar(select(Case).where(Case.id == run.case_id).with_for_update())
    doc = db.get(Document, run.payload.get("document_id"))
    if not case or not doc or not doc.active or doc.parse_status != "queued":
        return
    other = db.scalar(
        select(Run.id)
        .where(
            Run.case_id == run.case_id,
            Run.id != run.id,
            Run.kind == "parse",
            Run.status.in_(["queued", "running"]),
            Run.payload["document_id"].astext == doc.id,
        )
        .limit(1)
    )
    if other:
        return
    from .cases import bump

    ensure_parse(db, doc)
    append_parse(
        db,
        doc,
        {
            "pages": doc.pages,
            "status": "needs_review",
            "note": run.error or "解析已取消，可重新解析原件；未完成内容不视为已读取。",
        },
        "cancelled" if run.status == "cancelled" else "failed",
    )
    bump(db, case, "document.parse_cancelled", {"document_id": doc.id})


def parse_view(item):
    return {
        "id": item.id,
        "version": item.version,
        "parent_id": item.parent_id,
        "method": item.method,
        "status": item.status,
        "pages": item.pages,
        "fields": item.fields,
        "note": item.note,
        "engine": item.engine,
        "created_at": item.created_at.isoformat(),
    }


def correct_region(db, doc, body):
    previous = ensure_parse(db, doc)
    if previous.id != body.parse_revision_id:
        raise HTTPException(409, "解析版本已变化，请重新查看后校订")
    pages = deepcopy(previous.pages)
    page = next((p for p in pages if p["number"] == body.page), None)
    if not page:
        raise HTTPException(422, "页面不存在")
    if body.field_id:
        field = next(
            (f for f in previous.fields if f["id"] == body.field_id and f["page"] == body.page), None
        )
        if not field or page["text"].count(field["quote"]) != 1:
            raise HTTPException(409, "字段位置不唯一，请改用逐页校订")
        replacement = f"{field['label']}：{body.text}"
        page["text"] = page["text"].replace(field["quote"], replacement, 1)
        for region in page.get("regions", []):
            if region["id"] == field.get("region_id"):
                region.update(
                    text=replacement,
                    confirmed=True,
                    original_text=region.get("original_text", region["text"]),
                )
    else:
        page["text"] = body.text
        # Whole-page edits invalidate old text-to-region correspondences.
        page["regions"] = []
    if body.confirm_page:
        page["status"] = "ready"
        page["confirmed"] = True
    page["method"] = "user_corrected"
    fields = field_candidates(pages)
    for field in fields:
        field["confirmed"] = (
            bool(page.get("confirmed"))
            if field["page"] == body.page
            else any(
                f["id"] == field["id"] and f["quote"] == field["quote"] and f.get("confirmed")
                for f in previous.fields
            )
        )
        if body.field_id and field["id"] == body.field_id:
            field["confirmed"] = True
    return append_parse(
        db,
        doc,
        {
            "pages": pages,
            "status": "ready"
            if all(p.get("status", previous.status) == "ready" and p["text"].strip() for p in pages)
            else "needs_review",
            "note": "包含人工校订，请结合原件阅读；历史解析与原件均保留。",
            "engine": previous.engine,
        },
        "user_corrected",
        fields,
    )
