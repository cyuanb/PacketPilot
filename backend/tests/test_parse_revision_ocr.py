import io
import os
import shutil
from pathlib import Path

import pytest
from app.config import settings
from app.ocr import MODEL_FILES
from app.parsing import parse_file
from PIL import Image, ImageDraw, ImageFont


def test_scanned_pdf_without_engine_has_per_page_coverage(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "ocr_enabled", False)
    path = tmp_path / "scan.pdf"
    images = [Image.new("RGB", (400, 500), "white") for _ in range(2)]
    images[0].save(path, "PDF", save_all=True, append_images=images[1:])
    result = parse_file(path)
    assert result["status"] == "needs_review"
    assert len(result["pages"]) == 2 and all(p["status"] == "needs_review" for p in result["pages"])


def test_ocr_partial_failure_preserves_other_pages(tmp_path, monkeypatch):
    import app.parsing as parsing

    path = tmp_path / "scan.pdf"
    images = [Image.new("RGB", (300, 400), "white") for _ in range(2)]
    images[0].save(path, "PDF", save_all=True, append_images=images[1:])
    monkeypatch.setattr(parsing, "capabilities", lambda: {"available": True})

    def recognize(image, number):
        if number == 2:
            raise ValueError("synthetic page failure")
        return {
            "number": number,
            "label": "第 1 页",
            "text": "Readable synthetic first page",
            "method": "ocr",
            "status": "ready",
            "regions": [],
        }

    monkeypatch.setattr(parsing, "recognize", recognize)
    result = parse_file(path)
    assert result["status"] == "needs_review" and result["pages"][0]["status"] == "ready"
    assert result["pages"][1]["status"] != "ready"


def test_real_cpu_ocr_printed_image_and_pdf(tmp_path, monkeypatch):
    model_dir = os.getenv("OCR_TEST_MODEL_DIR")
    if not model_dir:
        pytest.skip("Explicit local OCR model directory not provided")
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    monkeypatch.setattr(settings, "ocr_enabled", True)
    target = tmp_path / "ocr-models"
    target.mkdir()
    for name in MODEL_FILES.values():
        shutil.copyfile(Path(model_dir) / name, target / name)
    from app.ocr import engine

    engine.cache_clear()
    fonts = [Path("C:/Windows/Fonts/arial.ttf"), Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")]
    font = ImageFont.truetype(str(next(p for p in fonts if p.is_file())), 40)
    image = Image.new("RGB", (1200, 650), "white")
    draw = ImageDraw.Draw(image)
    for y, line in enumerate(
        ["Application Form", "Name: Alice Chen", "Program: Computer Science", "Date: 2026-11-27"]
    ):
        draw.text((70, 80 + y * 90), line, font=font, fill="black")
    for suffix in ("png", "pdf"):
        path = tmp_path / f"synthetic.{suffix}"
        image.save(path)
        result = parse_file(path)
        assert result["status"] == "ready", result
        assert "Alice" in result["pages"][0]["text"]
        assert result["pages"][0]["regions"]
        assert all(
            0 <= v <= 1 for region in result["pages"][0]["regions"] for point in region["box"] for v in point
        )
    engine.cache_clear()


def test_parse_worker_and_preview_use_real_original(client, database):
    from app.worker import claim, process
    from test_workflow import case, current

    item = case(client)
    buffer = io.BytesIO()
    Image.new("RGB", (200, 200), "white").save(buffer, "PNG")
    response = client.post(
        f"/api/v1/cases/{item['id']}/documents",
        files={"file": ("synthetic.png", buffer.getvalue(), "image/png")},
    )
    assert response.status_code == 201
    doc_id = response.json()["document"]["id"]
    process(*claim())
    history = client.get(f"/api/v1/documents/{doc_id}/parses").json()
    assert len(history["items"]) == 2 and history["items"][0]["status"] == "needs_review"
    preview = client.get(f"/api/v1/documents/{doc_id}/pages/1/image")
    assert preview.is_success and preview.headers["content-type"].startswith("image/png")
    assert (
        client.post(
            f"/api/v1/documents/{doc_id}/parses", json={"revision": current(client, item)["revision"]}
        ).status_code
        == 202
    )
    assert (
        client.post(
            f"/api/v1/documents/{doc_id}/parses", json={"revision": current(client, item)["revision"]}
        ).status_code
        == 409
    )
    process(*claim())
    assert len(client.get(f"/api/v1/documents/{doc_id}/parses").json()["items"]) == 3
