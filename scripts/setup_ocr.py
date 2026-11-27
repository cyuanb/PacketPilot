"""Provision pinned public OCR model weights; never reads or uploads user documents."""

import hashlib
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.config import settings  # noqa: E402
from app.ocr import MODEL_FILES  # noqa: E402

BASE = "https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.10.0/onnx/PP-OCRv4/"
MODELS = {
    "Det": (
        "det/ch_PP-OCRv4_det_mobile.onnx",
        "d2a7720d45a54257208b1e13e36a8479894cb74155a5efe29462512d42f49da9",
    ),
    "Cls": (
        "cls/ch_ppocr_mobile_v2.0_cls_mobile.onnx",
        "e47acedf663230f8863ff1ab0e64dd2d82b838fceb5957146dab185a89d6215c",
    ),
    "Rec": (
        "rec/ch_PP-OCRv4_rec_mobile.onnx",
        "48fc40f24f6d2a207a2b1091d3437eb3cc3eb6b676dc3ef9c37384005483683b",
    ),
}


def main():
    target = settings.storage / "ocr-models"
    target.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=120, follow_redirects=True, trust_env=False) as client:
        for kind, (path, expected) in MODELS.items():
            destination = target / MODEL_FILES[kind]
            if destination.is_file() and hashlib.sha256(destination.read_bytes()).hexdigest() == expected:
                print(f"{kind}: already provisioned")
                continue
            temporary = destination.with_suffix(".download")
            try:
                digest = hashlib.sha256()
                size = 0
                with client.stream("GET", BASE + path) as response:
                    response.raise_for_status()
                    with temporary.open("wb") as handle:
                        for chunk in response.iter_bytes():
                            size += len(chunk)
                            if size > 100 * 1024 * 1024:
                                raise RuntimeError("Model exceeds expected size limit")
                            digest.update(chunk)
                            handle.write(chunk)
                if digest.hexdigest() != expected:
                    raise RuntimeError("Model checksum mismatch; no model was installed")
                temporary.replace(destination)
                print(f"{kind}: installed ({size} bytes), SHA256 verified")
            finally:
                temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
