import io
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..application.cases import bump, case_for, expect_revision
from ..application.documents import document_for
from ..application.packets import original_bytes
from ..application.parses import correct_region, parse_view
from ..application.runs import run_view
from ..db import get_db
from ..models import ParseRevision
from ..ocr import capabilities
from ..rendering import page_image
from ..schemas import RevisionInput
from .dependencies import current_user

router = APIRouter()


class PageCorrection(RevisionInput):
    parse_revision_id: str = Field(max_length=36)
    page: int = Field(ge=1, le=1000)
    field_id: str = Field(default="", max_length=100)
    text: str = Field(min_length=1, max_length=50000)
    confirm_page: bool = False


@router.get("/api/v1/capabilities/ocr")
def ocr_capabilities(user=Depends(current_user)):
    return capabilities()


@router.get("/api/v1/documents/{document_id}/parses")
def parse_history(document_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    d = document_for(db, user, document_id)
    return {
        "current_parse_id": d.current_parse_id,
        "items": [
            parse_view(p)
            for p in db.scalars(
                select(ParseRevision)
                .where(ParseRevision.document_id == d.id)
                .order_by(ParseRevision.version.desc())
            )
        ],
    }


@router.post("/api/v1/documents/{document_id}/parses", status_code=202)
def reparse(document_id: str, body: RevisionInput, user=Depends(current_user), db: Session = Depends(get_db)):
    d = document_for(db, user, document_id)
    c = case_for(db, user.id, d.case_id, True)
    expect_revision(c, body.revision)
    from ..application.parses import schedule_reparse

    db.refresh(d)
    r = schedule_reparse(db, c, d)
    db.commit()
    return run_view(r)


@router.post("/api/v1/documents/{document_id}/page-corrections")
def page_correction(
    document_id: str, body: PageCorrection, user=Depends(current_user), db: Session = Depends(get_db)
):
    d = document_for(db, user, document_id)
    c = case_for(db, user.id, d.case_id, True)
    expect_revision(c, body.revision)
    if not d.active or d.parse_status == "queued":
        raise HTTPException(409, "材料已替换或正在解析，请稍后重试")
    p = correct_region(db, d, body)
    bump(db, c, "document.page_corrected", {"document_id": d.id, "parse_revision_id": p.id})
    db.commit()
    return parse_view(p)


@router.get("/api/v1/documents/{document_id}/pages/{page}/image")
def preview_page(document_id: str, page: int, user=Depends(current_user), db: Session = Depends(get_db)):
    d = document_for(db, user, document_id)
    suffix = Path(d.filename).suffix.lower()
    if suffix not in (".pdf", ".png", ".jpg", ".jpeg") or page < 1:
        raise HTTPException(422, "仅 PDF 和图片提供逐页原件视图")
    try:
        raw = original_bytes(db, d)
        image = page_image(raw if suffix == ".pdf" else io.BytesIO(raw), suffix, page)
        output = io.BytesIO()
        image.save(output, "PNG")
    except (ValueError, OSError) as error:
        raise HTTPException(422, "原件页面暂不可显示") from error
    return Response(output.getvalue(), media_type="image/png")
