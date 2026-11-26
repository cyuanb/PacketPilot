"""Owner-controlled workspaces, subject profiles and explicit case roles."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..application.cases import case_for, expect_revision
from ..application.subjects import replace_case_subjects, subject_for, subject_view, update_subject
from ..application.views import case_view
from ..application.workspaces import personal_workspace, workspace_view
from ..db import get_db, now
from ..models import Case, CaseSubjectRole, SubjectProfile
from .dependencies import current_user
from .subject_requests import CaseSubjectsInput, SubjectInput, SubjectUpdate, WorkspaceUpdate

router = APIRouter()


@router.get("/api/v1/workspace")
def get_workspace(user=Depends(current_user), db: Session = Depends(get_db)):
    workspace = personal_workspace(db, user.id)
    db.commit()
    return workspace_view(workspace)


@router.patch("/api/v1/workspace")
def rename_workspace(body: WorkspaceUpdate, user=Depends(current_user), db: Session = Depends(get_db)):
    workspace = personal_workspace(db, user.id, True)
    expect_revision(workspace, body.revision)
    if workspace.name != body.name:
        workspace.name = body.name
        workspace.revision += 1
        workspace.updated_at = now()
    db.commit()
    return workspace_view(workspace)


@router.get("/api/v1/subjects")
def list_subjects(
    include_archived: bool = False,
    q: str = Query("", max_length=100),
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user=Depends(current_user),
    db: Session = Depends(get_db),
):
    workspace = personal_workspace(db, user.id)
    filters = [SubjectProfile.workspace_id == workspace.id]
    if not include_archived:
        filters.append(SubjectProfile.archived.is_(False))
    if q.strip():
        filters.append(
            or_(
                SubjectProfile.name.contains(q.strip(), autoescape=True),
                SubjectProfile.label.contains(q.strip(), autoescape=True),
            )
        )
    total = db.scalar(select(func.count()).select_from(SubjectProfile).where(*filters))
    rows = db.scalars(
        select(SubjectProfile)
        .where(*filters)
        .order_by(SubjectProfile.created_at.desc(), SubjectProfile.id)
        .offset(offset)
        .limit(limit)
    ).all()
    result = {
        "items": [subject_view(subject) for subject in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }
    db.commit()
    return result


@router.post("/api/v1/subjects", status_code=201)
def create_subject(body: SubjectInput, user=Depends(current_user), db: Session = Depends(get_db)):
    workspace = personal_workspace(db, user.id, True)
    subject = SubjectProfile(workspace_id=workspace.id, **body.model_dump())
    db.add(subject)
    db.commit()
    return subject_view(subject)


@router.get("/api/v1/subjects/{subject_id}")
def get_subject(subject_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    workspace = personal_workspace(db, user.id)
    subject = subject_for(db, workspace.id, subject_id)
    links = db.execute(
        select(CaseSubjectRole, Case)
        .join(Case, Case.id == CaseSubjectRole.case_id)
        .where(
            CaseSubjectRole.subject_id == subject.id,
            Case.workspace_id == workspace.id,
            Case.owner_id == user.id,
        )
        .order_by(Case.updated_at.desc())
    )
    return {
        **subject_view(subject),
        "cases": [{"id": c.id, "title": c.title, "role": link.role} for link, c in links],
    }


@router.patch("/api/v1/subjects/{subject_id}")
def edit_subject(
    subject_id: str, body: SubjectUpdate, user=Depends(current_user), db: Session = Depends(get_db)
):
    workspace = personal_workspace(db, user.id, True)
    subject = subject_for(db, workspace.id, subject_id)
    update_subject(db, subject, body)
    db.commit()
    return subject_view(subject)


@router.put("/api/v1/cases/{case_id}/subjects")
def assign_subjects(
    case_id: str, body: CaseSubjectsInput, user=Depends(current_user), db: Session = Depends(get_db)
):
    personal_workspace(db, user.id, True)
    case = case_for(db, user.id, case_id, True)
    replace_case_subjects(db, case, body)
    db.commit()
    return case_view(db, case, True)
