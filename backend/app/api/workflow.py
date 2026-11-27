from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..application.cases import case_for, expect_revision
from ..application.documents import document_for, remove_case_material
from ..application.issues import issues_view, set_issue_status, synchronize_issues
from ..application.library_links import bind_revision, linked_documents
from ..application.runs import enqueue, event, snapshot
from ..application.subjects import require_scenario_subject
from ..application.views import case_view
from ..application.workspaces import personal_workspace
from ..db import get_db
from ..models import Issue, IssueEvent, Run
from ..review.aggregation import review_result
from ..review.checks import run_checks
from ..scenarios import catalog
from ..schemas import RevisionInput
from .dependencies import current_user

router = APIRouter()


class LinkInput(RevisionInput):
    asset_revision_id: str = Field(min_length=1, max_length=36)
    purpose: Literal["source", "material"] = "material"
    category: str = Field(default="", max_length=100)


class IssueUpdate(RevisionInput):
    issue_revision: int = Field(ge=1)
    status: Literal["open", "requested", "submitted", "exception"]
    note: str = Field(default="", max_length=2000)


@router.get("/api/v1/scenarios")
def scenarios(user=Depends(current_user)):
    return catalog()


@router.get("/api/v1/cases/{case_id}/document-links")
def get_links(case_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    return linked_documents(db, case_for(db, user.id, case_id))


@router.post("/api/v1/cases/{case_id}/document-links", status_code=201)
def add_link(case_id: str, body: LinkInput, user=Depends(current_user), db: Session = Depends(get_db)):
    personal_workspace(db, user.id, True)
    case = case_for(db, user.id, case_id, True)
    expect_revision(case, body.revision)
    bind_revision(db, case, body.asset_revision_id, body.purpose, body.category)
    db.commit()
    return case_view(db, case, True)


@router.post("/api/v1/documents/{document_id}/library-version")
def choose_version(
    document_id: str, body: LinkInput, user=Depends(current_user), db: Session = Depends(get_db)
):
    personal_workspace(db, user.id, True)
    old = document_for(db, user, document_id)
    case = case_for(db, user.id, old.case_id, True)
    expect_revision(case, body.revision)
    bind_revision(db, case, body.asset_revision_id, old.purpose, old.category, old)
    db.commit()
    return case_view(db, case, True)


@router.delete("/api/v1/case-document-links/{document_id}")
def unlink_document(
    document_id: str, body: RevisionInput, user=Depends(current_user), db: Session = Depends(get_db)
):
    old = document_for(db, user, document_id)
    case = case_for(db, user.id, old.case_id, True)
    expect_revision(case, body.revision)
    return remove_case_material(db, user, document_id)


@router.post("/api/v1/cases/{case_id}/checks/basic")
def basic_check(case_id: str, body: RevisionInput, user=Depends(current_user), db: Session = Depends(get_db)):
    case = case_for(db, user.id, case_id, True)
    expect_revision(case, body.revision)
    inputs = snapshot(db, case)
    require_scenario_subject(db, case)
    if not inputs["requirements"]:
        raise HTTPException(409, "请先确认当前通知来源并启用要求")
    if db.scalar(
        select(Run.id)
        .where(Run.case_id == case.id, Run.kind != "parse", Run.status.in_(["queued", "running"]))
        .limit(1)
    ):
        raise HTTPException(409, "已有分析任务，请先等待完成或取消")
    run, _ = enqueue(db, case, "check", {"mode": "rules_only"})
    run.result = {**review_result(run.snapshot, run_checks(run.snapshot)), "mode": "rules_only"}
    run.model, run.status = "deterministic", "completed"
    case.current_check_id = run.id
    event(db, run.id, "run.completed", {"status": "completed", "mode": "rules_only"})
    synchronize_issues(db, case)
    db.commit()
    return case_view(db, case, True)


@router.get("/api/v1/cases/{case_id}/issues")
def list_issues(case_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    return issues_view(db, case_for(db, user.id, case_id))


@router.post("/api/v1/cases/{case_id}/issues/sync")
def sync_issues(case_id: str, body: RevisionInput, user=Depends(current_user), db: Session = Depends(get_db)):
    case = case_for(db, user.id, case_id, True)
    expect_revision(case, body.revision)
    synchronize_issues(db, case)
    db.commit()
    return issues_view(db, case)


@router.patch("/api/v1/issues/{issue_id}")
def edit_issue(issue_id: str, body: IssueUpdate, user=Depends(current_user), db: Session = Depends(get_db)):
    issue = db.get(Issue, issue_id)
    if not issue:
        raise HTTPException(404, "问题不存在")
    case = case_for(db, user.id, issue.case_id, True)
    expect_revision(case, body.revision)
    db.refresh(issue, with_for_update=True)
    set_issue_status(db, case, issue, body.status, body.note, body.issue_revision)
    db.commit()
    return issues_view(db, case)


@router.get("/api/v1/issues/{issue_id}/events")
def issue_history(issue_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    issue = db.get(Issue, issue_id)
    if not issue:
        raise HTTPException(404, "问题不存在")
    case_for(db, user.id, issue.case_id)
    return [
        {
            "action": event.action,
            "note": event.note,
            "case_revision": event.case_revision,
            "run_id": event.run_id,
            "at": event.created_at.isoformat(),
        }
        for event in db.scalars(
            select(IssueEvent)
            .where(IssueEvent.issue_id == issue.id)
            .order_by(IssueEvent.created_at, IssueEvent.id)
        )
    ]
