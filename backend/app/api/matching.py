from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field
from sqlalchemy.orm import Session

from ..application.cases import bump, case_for, expect_revision
from ..application.documents import doc_view, document_for, documents_for
from ..application.subjects import case_subjects
from ..db import get_db
from ..review.matching import MATERIAL_PROFILES, material_identity
from ..scenarios import scenario_snapshot
from ..schemas import RevisionInput
from .dependencies import current_user

router = APIRouter()


class AssignmentInput(RevisionInput):
    state: Literal["accepted", "rejected", "unassigned"]
    subject_id: str = Field(default="", max_length=36)
    document_type: str = Field(default="", max_length=100)
    slot_ids: list[str] = Field(default_factory=list, max_length=20)
    variant: Literal["original", "translation"] = "original"
    pair_key: str = Field(default="", max_length=100)
    issuer: str = Field(default="", max_length=200)


@router.get("/api/v1/cases/{case_id}/material-candidates")
def material_candidates(case_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    c = case_for(db, user.id, case_id)
    types = list(dict.fromkeys([*MATERIAL_PROFILES, *(c.scenario_snapshot or {}).get("materials", [])]))
    return [
        {
            "document_id": d.id,
            "assignment": d.assignment,
            "candidates": [
                {"document_type": name, **material_identity(doc_view(d), name)}
                for name in types
                if name == d.category or any(name in p["text"] for p in d.pages)
            ],
        }
        for d in documents_for(db, c.id)
        if d.purpose == "material"
    ]


@router.put("/api/v1/documents/{document_id}/assignment")
def assign_material(
    document_id: str, body: AssignmentInput, user=Depends(current_user), db: Session = Depends(get_db)
):
    d = document_for(db, user, document_id)
    c = case_for(db, user.id, d.case_id, True)
    expect_revision(c, body.revision)
    if not d.active or d.purpose != "material":
        raise HTTPException(409, "只能确认当前事项的有效材料")
    if body.subject_id and not any(
        s["subject_id"] == body.subject_id and not s["archived"] for s in case_subjects(db, c)
    ):
        raise HTTPException(422, "主体须先关联到本事项")
    if any(not s.strip() or len(s) > 100 for s in body.slot_ids):
        raise HTTPException(422, "槽位标识无效")
    if body.state == "accepted" and not body.document_type.strip():
        raise HTTPException(422, "请确认材料类型")
    d.assignment = body.model_dump(exclude={"revision"}) if body.state != "unassigned" else {}
    bump(db, c, "material.assignment_changed", {"document_id": d.id})
    db.commit()
    return doc_view(d)


@router.get("/api/v1/cases/{case_id}/scenario-update")
def scenario_update(case_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    c = case_for(db, user.id, case_id)
    current = c.scenario_snapshot or {}
    latest = scenario_snapshot(current.get("id"))
    return {"current": current, "latest": latest, "available": current != latest}


@router.post("/api/v1/cases/{case_id}/scenario-update")
def accept_scenario_update(
    case_id: str, body: RevisionInput, user=Depends(current_user), db: Session = Depends(get_db)
):
    c = case_for(db, user.id, case_id, True)
    expect_revision(c, body.revision)
    latest = scenario_snapshot((c.scenario_snapshot or {}).get("id"))
    if not latest:
        raise HTTPException(422, "通用事项没有场景模板更新")
    c.scenario_snapshot = latest
    bump(db, c, "scenario.updated", {"version": latest["version"]})
    db.commit()
    return {
        "scenario": latest,
        "notice": "已更新引导配置；已有要求和材料版本保持原样，请按新通知另建要求草稿",
    }
