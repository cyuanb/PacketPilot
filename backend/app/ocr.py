"""Local CPU OCR with explicit model provisioning; parsing never downloads models."""

import importlib.util
from functools import lru_cache

from .config import settings

MODEL_FILES = {
    "Det": "ch_PP-OCRv4_det_infer.onnx",
    "Cls": "ch_ppocr_mobile_v2.0_cls_infer.onnx",
    "Rec": "ch_PP-OCRv4_rec_infer.onnx",
}


def capabilities():
    installed = all(importlib.util.find_spec(name) for name in ("rapidocr", "onnxruntime", "pypdfium2"))
    models = all((settings.storage / "ocr-models" / name).is_file() for name in MODEL_FILES.values())
    return {
        "enabled": settings.ocr_enabled,
        "installed": installed,
        "models_ready": models,
        "available": bool(settings.ocr_enabled and installed and models),
        "engine": "RapidOCR / PP-OCRv4 / ONNX CPU",
        "max_pages": settings.ocr_max_pages,
        "min_score": settings.ocr_min_score,
        "scope": "清晰的中文/英文印刷体 PNG、JPEG 和扫描 PDF；手写、印章和复杂表格需人工复核",
    }


@lru_cache(maxsize=1)
def engine():
    if not capabilities()["available"]:
        raise ValueError("本机 OCR 不可用，请安装依赖并运行 OCR 模型准备脚本")
    from rapidocr import ModelType, OCRVersion, RapidOCR

    params = {
        "Global.text_score": 0.0,
        "Global.log_level": "error",
        "EngineConfig.onnxruntime.intra_op_num_threads": 2,
        "EngineConfig.onnxruntime.inter_op_num_threads": 1,
    }
    for kind, name in MODEL_FILES.items():
        params.update(
            {
                f"{kind}.model_path": str(settings.storage / "ocr-models" / name),
                f"{kind}.ocr_version": OCRVersion.PPOCRV4,
                f"{kind}.model_type": ModelType.MOBILE,
            }
        )
    return RapidOCR(params=params)


def recognize(image, number):
    import numpy as np

    width, height = image.size
    result = engine()(np.asarray(image.convert("RGB")))
    regions = []
    if result.txts:
        for i, (box, text, score) in enumerate(zip(result.boxes, result.txts, result.scores)):
            regions.append(
                {
                    "id": f"p{number}-r{i + 1}",
                    "text": text,
                    "confidence": float(score),
                    "box": [[float(x) / width, float(y) / height] for x, y in box],
                }
            )
    text = "\n".join(r["text"] for r in regions)
    good = (
        bool(regions)
        and len(regions) <= 2000
        and all(r["confidence"] >= settings.ocr_min_score for r in regions)
        and len(text) <= 50000
    )
    return {
        "number": number,
        "label": f"第 {number} 页",
        "text": text[:50000],
        "regions": regions[:2000],
        "width": width,
        "height": height,
        "method": "ocr",
        "status": "ready" if good else "needs_review",
    }
