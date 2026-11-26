"""HTTP endpoints for requirements."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..application.cases import bump, case_for, expect_revision
from ..application.documents import doc_view, documents_for
from ..application.requirements import save_rules
from ..application.views import case_view
from ..db import get_db
from ..models import RuleSet
from ..schemas import RevisionInput, RulesInput
from .dependencies import current_user

router = APIRouter()


@router.post("/api/v1/cases/{case_id}/rule-sets")
def edit_rules(case_id: str, body: RulesInput, user=Depends(current_user), db: Session = Depends(get_db)):
    c = case_for(db, user.id, case_id, True)
    expect_revision(c, body.revision)
    try:
        r = save_rules(
            db, c, [v.model_dump() for v in body.requirements], [doc_view(d) for d in documents_for(db, c.id)]
        )
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    db.commit()
    return {"id": r.id, "version": r.version}


@router.post("/api/v1/rule-sets/{rules_id}/activate")
def activate(rules_id: str, body: RevisionInput, user=Depends(current_user), db: Session = Depends(get_db)):
    r = db.get(RuleSet, rules_id)
    if not r:
        raise HTTPException(404, "要求版本不存在")
    c = case_for(db, user.id, r.case_id, True)
    expect_revision(c, body.revision)
    active_ids = {
        d.id for d in documents_for(db, c.id) if d.purpose == "source" and d.parse_status == "ready"
    }
    if r.status != "draft" or not set(r.source_ids).issubset(active_ids):
        raise HTTPException(409, "此草稿不可启用或来源版本已更新")
    if c.active_rules_id:
        db.get(RuleSet, c.active_rules_id).status = "superseded"
    r.status, c.active_rules_id = "active", r.id
    bump(db, c, "rules.activated", {"rules_id": r.id})
    db.commit()
    return case_view(db, c, True)
