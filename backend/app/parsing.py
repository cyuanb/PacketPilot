"""Bounded file readers. Documents never execute code or initiate network requests."""

import zipfile
from pathlib import Path

from docx import Document as WordDocument
from PIL import Image
from pypdf import PdfReader

from .config import settings
from .ocr import capabilities, recognize
from .rendering import page_image

MIMES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}


def validate_file(path: Path, suffix: str):
    head = path.read_bytes()[:16]
    if suffix == ".pdf" and not head.startswith(b"%PDF-"):
        raise ValueError("PDF 文件内容与扩展名不符")
    if suffix == ".docx":
        with zipfile.ZipFile(path) as z:
            entries = z.infolist()
            if len(entries) > 4000 or sum(i.file_size for i in entries) > 100 * 1024 * 1024:
                raise ValueError("DOCX 解压大小超过限制")
            if "word/document.xml" not in z.namelist():
                raise ValueError("不是有效的 DOCX 文档")
            if any("vbaProject" in i.filename for i in entries):
                raise ValueError("不接受含宏的文档")
    if suffix in (".png", ".jpg", ".jpeg"):
        with Image.open(path) as image:
            image.verify()


def parse_file(path: Path, max_pages=100):
    suffix = path.suffix.lower()
    if suffix not in MIMES:
        raise ValueError("暂不支持此格式")
    validate_file(path, suffix)
    pages, note, status = [], "", "ready"
    if suffix == ".pdf":
        reader = PdfReader(path)
        if reader.is_encrypted:
            raise ValueError("请上传未加密的 PDF 副本")
        if len(reader.pages) > max_pages:
            raise ValueError(f"PDF 超过 {max_pages} 页限制")
        for i, page in enumerate(reader.pages, 1):
            text = page.extract_text() or ""
            item = {
                "number": i,
                "label": f"第 {i} 页",
                "text": text[:50000],
                "method": "native",
                "status": "ready",
                "regions": [],
            }
            needs_ocr = len(text.strip()) < 10 or bool(page.images)
            if needs_ocr and i <= settings.ocr_max_pages and capabilities()["available"]:
                try:
                    item = recognize(page_image(path, suffix, i), i)
                    text = item["text"]
                except Exception:
                    item.update(status="failed", note="此页 OCR 失败，可重试或逐页校订")
            elif needs_ocr:
                item["status"] = "needs_review"
            if len(text.strip()) < 10 or len(text) > 50000:
                item["status"] = "needs_review"
            pages.append(item)
            if len(text.strip()) < 10 or len(text) > 50000:
                status = "needs_review"
                note = "部分页面无可读文本或超出读取上限；请预览原件或提供校订文本。"
    elif suffix == ".docx":
        doc = WordDocument(path)
        blocks = [p.text for p in doc.paragraphs if p.text.strip()]
        for table in doc.tables:
            blocks += [" | ".join(c.text for c in row.cells) for row in table.rows]
        pages = [{"number": i, "label": f"段落 {i}", "text": t[:50000]} for i, t in enumerate(blocks, 1)]
        if doc.inline_shapes:
            status, note = "needs_review", "包含图片；已读取段落和表格，图片内容仍需人工核对。"
        if any(len(b) > 50000 for b in blocks):
            status, note = "needs_review", "部分段落超出读取上限。"
    elif suffix in (".txt", ".md"):
        raw = path.read_bytes()
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = raw.decode("gb18030")
        pages = [{"number": 1, "label": "全文", "text": text}]
    else:
        if capabilities()["available"]:
            pages = [recognize(page_image(path, suffix), 1)]
        else:
            pages = [
                {
                    "number": 1,
                    "label": "第 1 页",
                    "text": "",
                    "status": "needs_review",
                    "regions": [],
                    "method": "unavailable",
                }
            ]
            status, note = "needs_review", "原件已保存，本机 OCR 未启用或模型未准备，可逐页校订。"
    if sum(len(p["text"]) for p in pages) > 500000:
        raise ValueError("材料文本超过 50 万字符限制，请拆分材料")
    if not any(p["text"].strip() for p in pages):
        status, note = "needs_review", note or "未读取到有效文本，请提供可读副本或校订文本。"
    if any(p.get("status", "ready") != "ready" for p in pages):
        status, note = "needs_review", note or "部分页面为空、识别低置信度或读取不完整，请逐页核对。"
    return {
        "pages": pages,
        "status": status,
        "note": note,
        "engine": "RapidOCR-PP-OCRv4" if any(p.get("method") == "ocr" for p in pages) else "native",
    }
