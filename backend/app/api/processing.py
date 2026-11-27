"""Bounded derivatives that enter the normal immutable document library."""

import hashlib
import io
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from PIL import Image, ImageOps
from pydantic import Field
from pypdf import PdfReader, PdfWriter
from sqlalchemy.orm import Session

from ..application.assets import capture_document, discard_uncommitted_file
from ..application.cases import bump, case_for, expect_revision
from ..application.documents import doc_view, documents_for
from ..application.packets import original_bytes
from ..application.runs import enqueue
from ..config import settings
from ..db import get_db, uid
from ..models import Document
from ..schemas import RevisionInput, StrictModel
from .dependencies import current_user

router = APIRouter()


class Selection(StrictModel):
    document_id: str
    pages: list[int] = Field(default_factory=list, max_length=100)
    rotation: Literal[0, 90, 180, 270] = 0


class ProcessInput(RevisionInput):
    title: str = Field(min_length=1, max_length=150)
    operation: Literal["pdf", "image"]
    selections: list[Selection] = Field(min_length=1, max_length=20)
    max_dimension: int = Field(default=1600, ge=300, le=4000)
    quality: int = Field(default=85, ge=40, le=95)


@router.post("/api/v1/cases/{case_id}/derivatives", status_code=201)
def derive(case_id: str, body: ProcessInput, user=Depends(current_user), db: Session = Depends(get_db)):
    c = case_for(db, user.id, case_id, True)
    expect_revision(c, body.revision)
    docs = {d.id: d for d in documents_for(db, c.id) if d.purpose == "material"}
    if len(docs) >= 30:
        raise HTTPException(422, "事项材料已满，请先移出不需要的材料")
    selected = []
    for entry in body.selections:
        d = docs.get(entry.document_id)
        if not d:
            raise HTTPException(404, "所选材料不可用")
        selected.append((entry, d, original_bytes(db, d)))
    output = io.BytesIO()
    provenance = []
    try:
        if body.operation == "pdf":
            writer = PdfWriter()
            count = 0
            for entry, d, raw in selected:
                if d.mime == "application/pdf":
                    reader = PdfReader(io.BytesIO(raw))
                    if reader.is_encrypted or len(reader.pages) > 100:
                        raise ValueError("加密或过长 PDF 不可加工")
                elif d.mime in ("image/png", "image/jpeg"):
                    with Image.open(io.BytesIO(raw)) as image:
                        if image.width * image.height > 40_000_000:
                            raise ValueError("图片过大")
                        converted = io.BytesIO()
                        ImageOps.exif_transpose(image).convert("RGB").save(converted, "PDF")
                        reader = PdfReader(converted)
                else:
                    raise ValueError("PDF 加工仅支持 PDF 或图片原件")
                pages = entry.pages or list(range(1, len(reader.pages) + 1))
                for n in pages:
                    if not 1 <= n <= len(reader.pages):
                        raise ValueError("页码越界")
                    count += 1
                    if count > 100:
                        raise ValueError("输出最多 100 页")
                    page = reader.pages[n - 1]
                    writer.add_page(page)
                    if entry.rotation:
                        writer.pages[-1].rotate(entry.rotation)
                    provenance.append(
                        {"document_id": d.id, "sha256": d.sha256, "page": n, "rotation": entry.rotation}
                    )
            writer.write(output)
            suffix, mime = ".pdf", "application/pdf"
            if len(PdfReader(io.BytesIO(output.getvalue())).pages) != count:
                raise ValueError("输出页数校验失败")
        else:
            if len(selected) != 1:
                raise ValueError("图片调整每次选择一份图片")
            entry, d, raw = selected[0]
            if d.mime not in ("image/png", "image/jpeg"):
                raise ValueError("请选择 PNG 或 JPEG")
            with Image.open(io.BytesIO(raw)) as image:
                if image.width * image.height > 40_000_000:
                    raise ValueError("图片过大")
                image = ImageOps.exif_transpose(image).convert("RGB").rotate(-entry.rotation, expand=True)
                image.thumbnail((body.max_dimension, body.max_dimension))
                image.save(output, "JPEG", quality=body.quality, optimize=True)
            suffix, mime = ".jpg", "image/jpeg"
            provenance = [
                {
                    "document_id": d.id,
                    "sha256": d.sha256,
                    "rotation": entry.rotation,
                    "max_dimension": body.max_dimension,
                    "quality": body.quality,
                }
            ]
        raw = output.getvalue()
        if len(raw) > settings.max_file_bytes:
            raise ValueError("派生文件超过单文件限制，请减少页数或尺寸")
    except (ValueError, OSError) as error:
        raise HTTPException(422, str(error)) from error
    key = uid() + suffix
    path = settings.storage / key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    try:
        d = Document(
            case_id=c.id,
            title=body.title,
            filename=Path(body.title).stem + suffix,
            storage_key=key,
            mime=mime,
            sha256=hashlib.sha256(raw).hexdigest(),
            size=len(raw),
            purpose="material",
            assignment={"derivation": provenance},
        )
        db.add(d)
        capture_document(db, c, d)
        bump(db, c, "material.derived", {"document_id": d.id})
        run, _ = enqueue(db, c, "parse", {"document_id": d.id})
        db.commit()
        return {
            "document": doc_view(d),
            "run_id": run.id,
            "provenance": provenance,
            "notice": "派生结果不替换原件；请核对页序、清晰度与签署有效性",
        }
    except Exception:
        discard_uncommitted_file(db, path)
        raise
