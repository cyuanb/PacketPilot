"""HTTP endpoints for documents."""

import hashlib
from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Response,
    UploadFile,
)
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..application.assets import (
    capture_document,
    discard_uncommitted_file,
    duplicate_versions,
    remove_unretained_files,
)
from ..application.cases import bump, case_for, expect_revision
from ..application.documents import doc_view, document_for, documents_for
from ..application.runs import enqueue
from ..config import settings
from ..db import get_db, uid
from ..models import Document, RuleSet, Run
from ..parsing import MIMES
from ..schemas import TextInput
from .dependencies import current_user
from .requests import CorrectionInput

router = APIRouter()


@router.post("/api/v1/cases/{case_id}/sources/text", status_code=201)
def text_source(case_id: str, body: TextInput, user=Depends(current_user), db: Session = Depends(get_db)):
    c = case_for(db, user.id, case_id, True)
    d = Document(
        case_id=c.id,
        title=body.title,
        purpose=body.purpose,
        category=body.category,
        filename=body.title + ".txt",
        mime="text/plain",
        size=len(body.text.encode()),
        sha256=hashlib.sha256(body.text.encode()).hexdigest(),
        parse_status="ready",
        pages=[{"number": 1, "label": "全文", "text": body.text}],
        parse_method="pasted",
    )
    db.add(d)
    capture_document(db, c, d)
    bump(db, c, "document.added")
    db.commit()
    return doc_view(d)


@router.post("/api/v1/cases/{case_id}/documents", status_code=201)
async def upload(
    case_id: str,
    file: UploadFile = File(...),
    purpose: str = Form("material"),
    category: str = Form(""),
    replace_id: str = Form(""),
    user=Depends(current_user),
    db: Session = Depends(get_db),
):
    c = case_for(db, user.id, case_id, True)
    if purpose not in ("source", "material") or len(category) > 100:
        raise HTTPException(422, "无效材料用途或分类")
    active = documents_for(db, c.id)
    if len(active) >= 30 and not replace_id:
        raise HTTPException(422, "每事项最多 30 份材料")
    filename = Path(file.filename or "file").name[:250]
    suffix = Path(filename).suffix.lower()
    if suffix not in MIMES:
        raise HTTPException(415, "支持 PDF、DOCX、TXT、MD、PNG 和 JPEG")
    raw = await file.read(settings.max_file_bytes + 1)
    if len(raw) > settings.max_file_bytes:
        raise HTTPException(413, "单文件不能超过 20 MiB")
    if not raw:
        raise HTTPException(422, "文件为空")
    previous = next((d for d in active if d.id == replace_id), None)
    if replace_id and not previous:
        raise HTTPException(409, "待替换材料已变化，请刷新")
    key = uid() + suffix
    settings.storage.mkdir(parents=True, exist_ok=True)
    path = settings.storage / key
    path.write_bytes(raw)
    try:
        d = Document(
            case_id=c.id,
            title=filename,
            purpose=previous.purpose if previous else purpose,
            category=category or (previous.category if previous else ""),
            filename=filename,
            storage_key=key,
            sha256=hashlib.sha256(raw).hexdigest(),
            mime=MIMES[suffix],
            size=len(raw),
        )
        if previous:
            previous.active = False
            d.logical_id, d.version = previous.logical_id, previous.version + 1
        db.add(d)
        capture_document(db, c, d, previous)
        bump(db, c, "document.replaced" if previous else "document.added")
        db.flush()
        task, _ = enqueue(db, c, "parse", {"document_id": d.id})
        duplicates = [
            match
            for match in duplicate_versions(db, c.workspace_id, d.sha256, d.size)
            if match["revision_id"] != d.asset_revision_id
        ]
        result = {"document": doc_view(d), "run_id": task.id, "duplicates": duplicates}
        db.commit()
        return result
    except Exception:
        discard_uncommitted_file(db, path)
        raise


@router.get("/api/v1/documents/{doc_id}")
def document_detail(doc_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    return doc_view(document_for(db, user, doc_id))


@router.get("/api/v1/documents/{doc_id}/content")
def document_content(doc_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    d = document_for(db, user, doc_id)
    if not d.storage_key:
        return Response("\n\n".join(p["text"] for p in d.pages), media_type="text/plain")
    path = settings.storage / d.storage_key
    if not path.is_file():
        raise HTTPException(404, "原件不存在")
    return FileResponse(
        path,
        media_type=d.mime,
        filename=d.filename,
        content_disposition_type="inline"
        if d.mime in ("application/pdf", "image/png", "image/jpeg")
        else "attachment",
    )


@router.post("/api/v1/documents/{doc_id}/correction")
def correction(doc_id: str, body: CorrectionInput, user=Depends(current_user), db: Session = Depends(get_db)):
    old = document_for(db, user, doc_id)
    c = case_for(db, user.id, old.case_id, True)
    expect_revision(c, body.revision)
    if not old.active:
        raise HTTPException(409, "材料已被替换")
    old.active = False
    d = Document(
        case_id=c.id,
        logical_id=old.logical_id,
        version=old.version + 1,
        title=old.title,
        purpose=old.purpose,
        category=old.category,
        filename=old.filename,
        mime=old.mime,
        storage_key=old.storage_key,
        sha256=old.sha256,
        size=old.size,
        parse_method="user_corrected",
        parse_status="ready",
        parse_note="用户提供校订文本；应结合原件复核。",
        pages=[{"number": 1, "label": "人工校订文本", "text": body.text}],
    )
    db.add(d)
    capture_document(db, c, d, old)
    bump(db, c, "document.corrected")
    db.commit()
    return doc_view(d)


@router.delete("/api/v1/documents/{doc_id}")
def delete_document(doc_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
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
