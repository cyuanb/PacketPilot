"""Validated, evidence-backed requirement-set persistence."""

from sqlalchemy import func, select

from ..models import RuleSet
from ..review.evidence import verify_evidence
from ..review.structure import validate_structure
from ..schemas import Requirement


def save_rules(db, case, requirements, documents):
    validated = [Requirement.model_validate(r).model_dump() for r in requirements]
    if not validated or len({r["id"] for r in validated}) != len(validated):
        raise ValueError("要求不能为空且标识不能重复")
    validate_structure(validated)
    for r in validated:
        verify_evidence(r["source_evidence"], documents, "source")
        for evidence in r["source_evidence"]:
            source = next(d for d in documents if d["id"] == evidence["document_id"])
            evidence["parse_revision_id"] = source.get("parse_revision_id")
    version = (db.scalar(select(func.max(RuleSet.version)).where(RuleSet.case_id == case.id)) or 0) + 1
    rules = RuleSet(
        case_id=case.id,
        version=version,
        requirements=validated,
        source_ids=list({e["document_id"] for r in validated for e in r["source_evidence"]}),
        source_versions={
            d["id"]: d.get("parse_revision_id")
            for d in documents
            if any(e["document_id"] == d["id"] for r in validated for e in r["source_evidence"])
        },
    )
    db.add(rules)
    db.flush()
    return rules
