"""HTTP endpoints for system."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import __version__
from ..config import settings
from ..db import get_db
from ..parsing import MIMES
from .dependencies import current_user

router = APIRouter()


@router.get("/api/health")
def health(db: Session = Depends(get_db)):
    from sqlalchemy import text

    db.execute(text("SELECT 1"))
    return {"status": "ok", "version": __version__}


@router.get("/api/v1/capabilities")
def capabilities(user=Depends(current_user)):
    from ..ocr import capabilities as ocr_capabilities

    return {
        "model": settings.llm_model,
        "model_configured": bool(settings.llm_api_key and settings.llm_base_url),
        "ocr": ocr_capabilities()["available"],
        "formats": list(MIMES),
        "max_file_mb": 20,
        "inference": "所需文本片段会发送至配置的模型服务，原件保存在本机。",
    }


@router.post("/api/v1/model/check")
def model_check(user=Depends(current_user)):
    import httpx

    try:
        with httpx.Client(timeout=20, trust_env=False) as client:
            r = client.post(
                settings.llm_base_url.rstrip("/") + "/chat/completions",
                headers={"Authorization": "Bearer " + settings.llm_api_key},
                json={
                    "model": settings.llm_model,
                    "messages": [{"role": "user", "content": "请回复连接正常。"}],
                    "max_tokens": 30,
                },
            )
            return {"ok": r.is_success, "status": r.status_code, "model": settings.llm_model}
    except Exception:
        return {"ok": False, "message": "模型服务暂时无法连接，请检查内网连接和本地配置"}
