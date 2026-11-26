"""Current review reports reconciled with persisted revisions and evidence."""

from sqlalchemy import select

from ..models import Attestation, RuleSet, Run
from ..review.aggregation import assess_results, requirements_fingerprint
from ..review.version import REVIEW_ENGINE_VERSION
from .documents import documents_for


def checklist(db, case):
    run = db.get(Run, case.current_check_id) if case.current_check_id else None
    findings = run.result.get("findings", []) if run else []
    stale = bool(run and run.revision != case.revision)
    rules = db.get(RuleSet, case.active_rules_id) if case.active_rules_id else None
    source_ids = {
        d.id for d in documents_for(db, case.id) if d.purpose == "source" and d.parse_status == "ready"
    }
    if rules and not set(rules.source_ids).issubset(source_ids):
        stale = True
    requirements = rules.requirements if rules else []
    engine_version = run.result.get("engine_version") if run else None
    legacy = bool(run and engine_version is None)
    stale_reason = "材料、背景或通知来源已经变化，请重新预检。" if stale else ""
    if run and engine_version != REVIEW_ENGINE_VERSION:
        stale = True
        stale_reason = (
            "这是旧版引擎生成的历史结果，请重新预检。" if legacy else "检查引擎已更新，请重新预检。"
        )
    if (
        run
        and rules
        and (
            run.snapshot.get("rules_id") != rules.id
            or run.result.get("rules_id") != rules.id
            or run.result.get("requirements_fingerprint") != requirements_fingerprint(requirements)
        )
    ):
        stale = True
        if not stale_reason:
            stale_reason = "要求版本或内容与本次检查不一致，请重新预检。"
    confirmations = list(
        db.scalars(
            select(Attestation).where(Attestation.case_id == case.id, Attestation.revision == case.revision)
        )
    )
    report = assess_results(
        requirements, findings, case.facts, stale=stale, confirmed=[a.requirement_id for a in confirmations]
    )
    terminal = bool(run and run.status in ("completed", "waiting_for_input"))
    status = report["status"]
    if not rules or not run or (not stale and run.status in ("queued", "running")):
        status = "not_ready"
    elif not stale and not terminal:
        status = "needs_review"
    can_export = bool(run and rules and not stale and terminal and report["coverage"]["complete"])
    return {
        "status": status,
        "stale": stale,
        "findings": report["findings"],
        "coverage": report["coverage"],
        "advisory_count": report["advisory_count"],
        "engine_version": engine_version or ("legacy" if run else None),
        "legacy": legacy,
        "stale_reason": stale_reason,
        "run_status": run.status if run else None,
        "can_export": can_export,
        "run_id": run.id if run else None,
        "revision": case.revision,
        "checked_revision": run.revision if run else None,
        "checked_at": run.updated_at.isoformat() if run else None,
        "requirements": requirements,
        "attestations": [
            {"requirement_id": a.requirement_id, "note": a.note, "created_at": a.created_at.isoformat()}
            for a in confirmations
        ],
    }
