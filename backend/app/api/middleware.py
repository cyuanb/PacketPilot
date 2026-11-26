"""Origin checks, response headers and HTTP error representation."""

import secrets

from fastapi import Request
from fastapi.responses import JSONResponse

from ..config import settings


async def request_boundary(request: Request, call_next):
    request_id = secrets.token_hex(8)
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        origin = request.headers.get("origin")
        allowed = {settings.app_origin, "http://localhost:5173", "http://127.0.0.1:5173"}
        if (origin and origin not in allowed) or (not origin and request.headers.get("x-packetpilot") != "1"):
            return JSONResponse(
                {"code": "origin_rejected", "message": "请求来源无效", "request_id": request_id},
                status_code=403,
            )
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Cache-Control"] = "no-store" if request.url.path.startswith("/api") else "no-cache"
    return response


async def http_error(request, exc):
    return JSONResponse(
        {"code": f"http_{exc.status_code}", "message": exc.detail}, status_code=exc.status_code
    )
