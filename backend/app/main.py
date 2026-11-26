"""FastAPI application assembly and static frontend mounting."""

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from .api import cases, documents, identity, reports, requirements, runs, subjects, system
from .api.identity import login_attempts as login_attempts
from .api.middleware import http_error, request_boundary
from .config import ROOT
from .db import SessionLocal as SessionLocal


def create_app():
    app = FastAPI(title="PacketPilot API", version="0.1.1", docs_url="/api/docs")
    app.middleware("http")(request_boundary)
    app.add_exception_handler(HTTPException, http_error)
    for router in (
        identity.router,
        system.router,
        cases.router,
        documents.router,
        requirements.router,
        runs.router,
        reports.router,
        subjects.router,
    ):
        app.include_router(router)
    dist = ROOT / "frontend" / "dist"
    if dist.exists():
        app.mount("/", StaticFiles(directory=dist, html=True), name="web")
    return app


app = create_app()
