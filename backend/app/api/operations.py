"""Content-minimizing diagnostics and explicit retry of failed work."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..application.cases import case_for
from ..application.runs import run_for, run_view
from ..db import get_db
from ..models import Case, Document, Run
from .dependencies import current_user

router = APIRouter()


@router.get("/api/v1/diagnostics")
def diagnostics(user=Depends(current_user), db: Session = Depends(get_db)):
    runs = list(
        db.scalars(
            select(Run)
            .join(Case, Case.id == Run.case_id)
            .where(Case.owner_id == user.id)
            .order_by(Run.created_at.desc())
            .limit(100)
        )
    )
    return {
        "limits": {
            "max_file_mib": 20,
            "max_case_documents": 30,
            "max_pending_jobs": 10,
            "max_model_steps": 8,
        },
        "jobs": [
            {
                "id": r.id,
                "case_id": r.case_id,
                "kind": r.kind,
                "status": r.status,
                "attempt": r.attempt,
                "updated_at": r.updated_at.isoformat(),
                "error": r.error,
            }
            for r in runs
        ],
    }


@router.post("/api/v1/runs/{run_id}/retry", status_code=202)
def retry(run_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    old = run_for(db, user, run_id)
    c = case_for(db, user.id, old.case_id, True)
    if old.status not in ("failed", "cancelled"):
        raise HTTPException(409, "只有失败或取消的任务可以重试")
    if old.kind == "parse":
        d = db.get(Document, old.payload.get("document_id"))
        if not d or not d.active:
            raise HTTPException(409, "材料版本已失效")
        from ..application.parses import schedule_reparse

        r = schedule_reparse(db, c, d)
    else:
        from ..application.runs import start_run

        return start_run(
            db,
            user,
            c.id,
            old.kind,
            c.revision,
            {k: v for k, v in old.payload.items() if k != "_digest"},
            None,
        )
    db.commit()
    return run_view(r)
