"""HTTP endpoints for runs."""

import asyncio
import json

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Request,
)
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import db as db_module
from ..application.runs import run_for, run_view, start_run
from ..db import get_db
from ..models import Run, RunEvent
from ..schemas import ChatInput, RevisionInput
from .dependencies import current_user

router = APIRouter()


@router.get("/api/v1/agent/skills")
def skill_catalog(user=Depends(current_user)):
    from ..agent_skills import SKILLS, load_skill

    return [load_skill(name)[1] for name in SKILLS]


@router.post("/api/v1/cases/{case_id}/extract", status_code=202)
def extract(
    case_id: str,
    body: RevisionInput,
    user=Depends(current_user),
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(None),
):
    return start_run(db, user, case_id, "extract", body.revision, {}, idempotency_key)


@router.post("/api/v1/cases/{case_id}/checks", status_code=202)
def check(
    case_id: str,
    body: RevisionInput,
    user=Depends(current_user),
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(None),
):
    return start_run(db, user, case_id, "check", body.revision, {}, idempotency_key)


@router.post("/api/v1/cases/{case_id}/messages", status_code=202)
def chat(
    case_id: str,
    body: ChatInput,
    user=Depends(current_user),
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(None),
):
    return start_run(db, user, case_id, "chat", body.revision, {"text": body.text}, idempotency_key)


@router.get("/api/v1/runs/{run_id}")
def get_run(run_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    return run_view(run_for(db, user, run_id))


@router.post("/api/v1/runs/{run_id}/cancel")
def cancel(run_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    r = run_for(db, user, run_id)
    r.cancel_requested = True
    if r.status == "queued":
        r.status = "cancelled"
    db.commit()
    return {"status": r.status, "cancel_requested": True}


@router.get("/api/v1/runs/{run_id}/events")
async def events(
    run_id: str, request: Request, after: int = 0, user=Depends(current_user), db: Session = Depends(get_db)
):
    run_for(db, user, run_id)
    try:
        cursor = max(after, int(request.headers.get("last-event-id", "0")))
    except ValueError:
        raise HTTPException(422, "无效事件游标")

    async def stream():
        nonlocal cursor
        while not await request.is_disconnected():
            with db_module.SessionLocal() as session:
                r = session.get(Run, run_id)
                if not r:
                    break
                batch = list(
                    session.scalars(
                        select(RunEvent)
                        .where(RunEvent.run_id == run_id, RunEvent.id > cursor)
                        .order_by(RunEvent.id)
                        .limit(100)
                    )
                )
                terminal = r.status not in ("queued", "running")
                for e in batch:
                    cursor = e.id
                    yield f"id: {e.id}\nevent: {e.event}\ndata: {json.dumps(e.data, ensure_ascii=False)}\n\n"
            if terminal and len(batch) < 100:
                yield "event: done\ndata: {}\n\n"
                break
            yield ": heartbeat\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"X-Accel-Buffering": "no"})
