"""HTTP endpoints for requirements."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..application.cases import bump, case_for, expect_revision
from ..application.documents import doc_view, documents_for
from ..application.requirements import save_rules
from ..application.runs import snapshot
from ..application.views import case_view
from ..db import get_db
from ..models import RuleSet
from ..review.aggregation import assess_results
from ..review.checks import run_checks
from ..review.structure import source_conflicts, source_versions_valid, validate_structure
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
    if r.status != "draft" or not source_versions_valid(r, documents_for(db, c.id)):
        raise HTTPException(409, "此草稿不可启用或来源版本已更新")
    if any(not conflict["resolved"] for conflict in source_conflicts(r.requirements)):
        raise HTTPException(422, "存在未处理的多来源规则冲突，请先比较来源并选择要求或填写处理说明")
    if c.active_rules_id:
        db.get(RuleSet, c.active_rules_id).status = "superseded"
    r.status, c.active_rules_id = "active", r.id
    bump(db, c, "rules.activated", {"rules_id": r.id})
    db.commit()
    return case_view(db, c, True)


@router.post("/api/v1/cases/{case_id}/rules/preview")
def preview_rules(case_id: str, body: RulesInput, user=Depends(current_user), db: Session = Depends(get_db)):
    from ..review.evidence import verify_evidence

    c = case_for(db, user.id, case_id)
    expect_revision(c, body.revision)
    inputs = snapshot(db, c)
    values = [r.model_dump() for r in body.requirements]
    try:
        validate_structure(values)
        for r in values:
            verify_evidence(r["source_evidence"], inputs["documents"], "source")
        inputs["requirements"] = values
        findings = run_checks(inputs)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    return {
        "conflicts": source_conflicts(values),
        "report": assess_results(values, findings, inputs["facts"]),
        "notice": "仅草稿试运行，不改变启用要求、检查报告或补件状态",
    }
