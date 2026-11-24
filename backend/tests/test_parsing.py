import pytest
from app.parsing import parse_file
from docx import Document
from PIL import Image
from pypdf import PdfWriter


def test_utf8_and_gb_text(tmp_path):
    for encoding in ("utf-8", "gb18030"):
        p = tmp_path / "材料.txt"
        p.write_bytes("成绩单\n姓名：李沐".encode(encoding))
        result = parse_file(p)
        assert result["status"] == "ready" and "李沐" in result["pages"][0]["text"]


def test_blank_pdf_requires_review(tmp_path):
    p = tmp_path / "scan.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.write(p)
    assert parse_file(p)["status"] == "needs_review"


def test_encrypted_and_disguised_pdf_rejected(tmp_path):
    p = tmp_path / "locked.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.encrypt("password")
    writer.write(p)
    with pytest.raises(ValueError):
        parse_file(p)
    p.write_text("<html>not pdf</html>")
    with pytest.raises(ValueError):
        parse_file(p)


def test_docx_preserves_table_text(tmp_path):
    p = tmp_path / "application.docx"
    d = Document()
    d.add_paragraph("申请表")
    d.add_table(rows=1, cols=2).cell(0, 0).text = "姓名：李沐"
    d.save(p)
    assert any("李沐" in page["text"] for page in parse_file(p)["pages"])


def test_image_is_never_claimed_as_read(tmp_path):
    p = tmp_path / "photo.png"
    Image.new("RGB", (20, 20), "white").save(p)
    result = parse_file(p)
    assert result["status"] == "needs_review" and result["pages"] == []
