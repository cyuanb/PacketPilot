"""HTTP endpoints for cases."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..application.assets import remove_unretained_files
from ..application.cases import bump, case_for, expect_revision
from ..application.views import case_view
from ..application.workspaces import personal_workspace
from ..db import get_db
from ..models import Audit, Case, Document, Membership, Workspace
from ..schemas import CaseInput, FactInput
from .dependencies import current_user
from .requests import CaseUpdate

router = APIRouter()


@router.get("/api/v1/cases")
def list_cases(user=Depends(current_user), db: Session = Depends(get_db)):
    return [
        case_view(db, c)
        for c in db.scalars(
            select(Case)
            .join(Workspace, Workspace.id == Case.workspace_id)
            .join(Membership, Membership.workspace_id == Workspace.id)
            .where(
                Case.owner_id == user.id,
                Workspace.owner_id == user.id,
                Membership.user_id == user.id,
                Membership.role == "owner",
            )
            .order_by(Case.updated_at.desc())
        )
    ]


@router.post("/api/v1/cases", status_code=201)
def create_case(body: CaseInput, user=Depends(current_user), db: Session = Depends(get_db)):
    workspace = personal_workspace(db, user.id)
    c = Case(owner_id=user.id, workspace_id=workspace.id, **body.model_dump())
    db.add(c)
    db.commit()
    return case_view(db, c, True)


@router.get("/api/v1/cases/{case_id}")
def get_case(case_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    return case_view(db, case_for(db, user.id, case_id), True)


@router.patch("/api/v1/cases/{case_id}")
def update_case(case_id: str, body: CaseUpdate, user=Depends(current_user), db: Session = Depends(get_db)):
    c = case_for(db, user.id, case_id, True)
    expect_revision(c, body.revision)
    for k, v in body.model_dump(exclude={"revision"}).items():
        setattr(c, k, v)
    bump(db, c, "case.updated")
    db.commit()
    return case_view(db, c, True)


@router.delete("/api/v1/cases/{case_id}")
def delete_case(case_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    c = case_for(db, user.id, case_id, True)
    keys = list(db.scalars(select(Document.storage_key).where(Document.case_id == c.id)))
    db.delete(c)
    db.commit()
    remove_unretained_files(db, keys)
    return {"ok": True}


@router.post("/api/v1/cases/{case_id}/facts/confirm")
def facts(case_id: str, body: FactInput, user=Depends(current_user), db: Session = Depends(get_db)):
    c = case_for(db, user.id, case_id, True)
    expect_revision(c, body.revision)
    if any(len(k) > 100 or len(str(v)) > 1000 for k, v in body.facts.items()):
        raise HTTPException(422, "背景字段过长")
    c.facts = body.facts
    bump(db, c, "facts.confirmed")
    db.commit()
    return case_view(db, c, True)


@router.get("/api/v1/cases/{case_id}/audit")
def audit(case_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    c = case_for(db, user.id, case_id)
    return [
        {"action": a.action, "data": a.data, "at": a.created_at.isoformat()}
        for a in db.scalars(select(Audit).where(Audit.case_id == c.id).order_by(Audit.id.desc()).limit(100))
    ]


@router.post("/api/v1/demo", status_code=201)
def demo(user=Depends(current_user), db: Session = Depends(get_db)):
    from ..demo import create_demo

    c = create_demo(db, user.id)
    db.commit()
    return case_view(db, c, True)
