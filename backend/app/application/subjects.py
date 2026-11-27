"""Distinct profiles and explicitly scoped case roles; names never act as identity keys."""

from fastapi import HTTPException
from sqlalchemy import delete, select

from ..db import now
from ..models import Case, CaseSubjectRole, SubjectProfile
from .cases import bump, expect_revision


def subject_for(db, workspace_id, subject_id):
    subject = db.scalar(
        select(SubjectProfile).where(
            SubjectProfile.id == subject_id, SubjectProfile.workspace_id == workspace_id
        )
    )
    if not subject:
        raise HTTPException(404, "主体档案不存在")
    return subject


def subject_view(subject):
    return {
        "id": subject.id,
        "workspace_id": subject.workspace_id,
        "kind": subject.kind,
        "name": subject.name,
        "label": subject.label,
        "attributes": subject.attributes,
        "archived": subject.archived,
        "revision": subject.revision,
        "created_at": subject.created_at.isoformat(),
        "updated_at": subject.updated_at.isoformat(),
    }


def case_subjects(db, case):
    rows = db.execute(
        select(CaseSubjectRole, SubjectProfile)
        .join(
            SubjectProfile,
            (SubjectProfile.id == CaseSubjectRole.subject_id)
            & (SubjectProfile.workspace_id == CaseSubjectRole.workspace_id),
        )
        .where(CaseSubjectRole.case_id == case.id, CaseSubjectRole.workspace_id == case.workspace_id)
        .order_by(CaseSubjectRole.role, SubjectProfile.id)
    )
    # Only the identity context is attached to a run; contact attributes are not sent to the agent.
    return [
        {
            "subject_id": subject.id,
            "role": link.role,
            "kind": subject.kind,
            "name": subject.name,
            "label": subject.label,
            "revision": subject.revision,
            "archived": subject.archived,
        }
        for link, subject in rows
    ]


def update_subject(db, subject, body):
    if subject.revision != body.revision:
        raise HTTPException(409, "主体档案已变化，请刷新后重试")
    if body.kind != subject.kind:
        raise HTTPException(422, "个人与组织类型不能互换，请另建独立档案")
    values = body.model_dump(exclude={"revision", "kind"})
    if all(getattr(subject, key) == value for key, value in values.items()):
        return subject
    cases = list(
        db.scalars(
            select(Case)
            .where(
                Case.workspace_id == subject.workspace_id,
                Case.id.in_(select(CaseSubjectRole.case_id).where(CaseSubjectRole.subject_id == subject.id)),
            )
            .order_by(Case.id)
            .with_for_update()
        )
    )
    for key, value in values.items():
        setattr(subject, key, value)
    subject.revision += 1
    subject.updated_at = now()
    for case in cases:
        bump(db, case, "subject.updated", {"subject_id": subject.id, "subject_revision": subject.revision})
    return subject


def replace_case_subjects(db, case, body):
    expect_revision(case, body.revision)
    existing = {
        (link.subject_id, link.role)
        for link in db.scalars(select(CaseSubjectRole).where(CaseSubjectRole.case_id == case.id))
    }
    proposed = [(link.subject_id, link.role) for link in body.links]
    if len(proposed) != len(set(proposed)):
        raise HTTPException(422, "同一主体与角色不能重复添加")
    for subject_id, role in proposed:
        subject = subject_for(db, case.workspace_id, subject_id)
        expected_kind = case.scenario_snapshot.get("primary_subject_kind")
        if role == "applicant" and expected_kind and subject.kind != expected_kind:
            raise HTTPException(422, "申请主体类型与当前场景不符，请选择对应的个人或组织档案")
        if subject.archived and (subject_id, role) not in existing:
            raise HTTPException(409, "已归档主体不能新增关联，请先恢复档案")
        if (role in {"recommender", "representative", "contact"} and subject.kind != "person") or (
            role == "organization" and subject.kind != "organization"
        ):
            raise HTTPException(422, "主体类型与所选角色不符")
    if set(proposed) == existing:
        return
    db.execute(delete(CaseSubjectRole).where(CaseSubjectRole.case_id == case.id))
    db.add_all(
        [
            CaseSubjectRole(case_id=case.id, workspace_id=case.workspace_id, subject_id=s, role=r)
            for s, r in proposed
        ]
    )
    bump(db, case, "subjects.changed", {"links": [link.model_dump() for link in body.links]})
    db.flush()


def require_scenario_subject(db, case):
    if case.scenario_snapshot and not db.scalar(
        select(CaseSubjectRole.subject_id)
        .where(CaseSubjectRole.case_id == case.id, CaseSubjectRole.role == "applicant")
        .limit(1)
    ):
        raise HTTPException(422, "请先在事项主体中关联本场景的申请主体")
