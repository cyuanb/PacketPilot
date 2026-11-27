"""Current review reports reconciled with persisted revisions and evidence."""

from datetime import date
from zoneinfo import ZoneInfo

from sqlalchemy import select

from ..db import now
from ..models import Attestation, RuleSet, Run
from ..review.aggregation import assess_results, requirements_fingerprint
from ..review.structure import source_versions_valid
from ..review.version import REVIEW_ENGINE_VERSION
from .documents import documents_for


def checklist(db, case):
    run = db.get(Run, case.current_check_id) if case.current_check_id else None
    findings = run.result.get("findings", []) if run else []
    stale = bool(run and run.revision != case.revision)
    rules = db.get(RuleSet, case.active_rules_id) if case.active_rules_id else None
    if rules and not source_versions_valid(rules, documents_for(db, case.id)):
        stale = True
    requirements = rules.requirements if rules else []
    today = now().astimezone(ZoneInfo(case.timezone)).date().isoformat()
    time_changed = bool(
        run
        and any(
            r.get("parameters", {}).get("reference") == "today" or "max_age_days" in r.get("parameters", {})
            for r in requirements
        )
        and run.snapshot.get("reference_date") != today
    )
    expired = any(
        r.get("parameters", {}).get("source_valid_until")
        and date.fromisoformat(r["parameters"]["source_valid_until"]) < date.fromisoformat(today)
        for r in requirements
    )
    if time_changed or expired:
        stale = True
    engine_version = run.result.get("engine_version") if run else None
    legacy = bool(run and engine_version is None)
    stale_reason = "材料、背景或通知来源已经变化，请重新预检。" if stale else ""
    if expired:
        stale_reason = "要求来源已过有效日期，请重新确认通知和要求。"
    elif time_changed:
        stale_reason = "日期参照已变化，请重新核对有效期间。"
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
