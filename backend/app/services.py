import hashlib
import json

from fastapi import HTTPException
from sqlalchemy import func, select

from .db import now
from .domain import REVIEW_ENGINE_VERSION, assess_results, requirements_fingerprint, verify_evidence
from .models import Attestation, Audit, Case, Document, Message, RuleSet, Run, RunEvent
from .schemas import Requirement


def case_for(db, user_id, case_id, lock=False):
    query = select(Case).where(Case.id == case_id, Case.owner_id == user_id)
    if lock:
        query = query.with_for_update()
    item = db.scalar(query)
    if not item:
        raise HTTPException(404, "事项不存在")
    return item


def expect_revision(case, revision):
    if case.revision != revision:
        raise HTTPException(409, "材料或要求已变化，请刷新后重试")


def bump(db, case, action, data=None):
    case.revision += 1
    case.updated_at = now()
    db.add(Audit(case_id=case.id, action=action, data=data or {}))


def doc_view(d, include_text=True):
    return {
        "id": d.id,
        "logical_id": d.logical_id,
        "version": d.version,
        "title": d.title,
        "purpose": d.purpose,
        "category": d.category,
        "filename": d.filename,
        "mime": d.mime,
        "size": d.size,
        "parse_status": d.parse_status,
        "parse_note": d.parse_note,
        "parse_method": d.parse_method,
        "active": d.active,
        "pages": d.pages if include_text else [],
        "page_count": len(d.pages),
        "created_at": d.created_at.isoformat(),
    }


def documents_for(db, case_id):
    return list(
        db.scalars(
            select(Document).where(Document.case_id == case_id, Document.active).order_by(Document.created_at)
        )
    )


def snapshot(db, case):
    rules = db.get(RuleSet, case.active_rules_id) if case.active_rules_id else None
    docs = documents_for(db, case.id)
    source_ids = {d.id for d in docs if d.purpose == "source" and d.parse_status == "ready"}
    valid_rules = bool(rules and set(rules.source_ids).issubset(source_ids))
    return {
        "case_id": case.id,
        "title": case.title,
        "revision": case.revision,
        "deadline": case.deadline,
        "reference_date": now().astimezone().date().isoformat(),
        "facts": case.facts,
        "rules_id": case.active_rules_id,
        "requirements": rules.requirements if valid_rules else [],
        "documents": [doc_view(d) for d in docs],
    }


def event(db, run_id, kind, data=None):
    db.add(RunEvent(run_id=run_id, event=kind, data=data or {}))


def enqueue(db, case, kind, payload=None, key=None):
    payload = payload or {}
    digest = hashlib.sha256(
        json.dumps({"kind": kind, "payload": payload}, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
    if key:
        prior = db.scalar(select(Run).where(Run.case_id == case.id, Run.idempotency_key == key))
        if prior:
            if prior.payload.get("_digest") != digest:
                raise HTTPException(409, "相同请求标识不能用于不同操作")
            return prior, False
    item = Run(
        case_id=case.id,
        kind=kind,
        revision=case.revision,
        payload={**payload, "_digest": digest},
        snapshot=snapshot(db, case),
        idempotency_key=key,
    )
    db.add(item)
    db.flush()
    event(db, item.id, "run.queued", {"kind": kind})
    return item, True


def save_rules(db, case, requirements, documents):
    validated = [Requirement.model_validate(r).model_dump() for r in requirements]
    if not validated or len({r["id"] for r in validated}) != len(validated):
        raise ValueError("要求不能为空且标识不能重复")
    for r in validated:
        verify_evidence(r["source_evidence"], documents, "source")
    version = (db.scalar(select(func.max(RuleSet.version)).where(RuleSet.case_id == case.id)) or 0) + 1
    rules = RuleSet(
        case_id=case.id,
        version=version,
        requirements=validated,
        source_ids=list({e["document_id"] for r in validated for e in r["source_evidence"]}),
    )
    db.add(rules)
    db.flush()
    return rules


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


def case_view(db, c, detail=False):
    result = {
        "id": c.id,
        "title": c.title,
        "institution": c.institution,
        "kind": c.kind,
        "deadline": c.deadline,
        "revision": c.revision,
        "archived": c.archived,
        "facts": c.facts,
        "created_at": c.created_at.isoformat(),
        "updated_at": c.updated_at.isoformat(),
        "checklist": checklist(db, c),
    }
    if detail:
        result["documents"] = [doc_view(d, False) for d in documents_for(db, c.id)]
        result["rule_sets"] = [
            {"id": r.id, "version": r.version, "status": r.status, "requirements": r.requirements}
            for r in db.scalars(
                select(RuleSet).where(RuleSet.case_id == c.id).order_by(RuleSet.version.desc())
            )
        ]
        result["messages"] = [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at.isoformat(),
                "run_id": m.run_id,
            }
            for m in db.scalars(
                select(Message)
                .where(Message.case_id == c.id, Message.role.in_(["user", "assistant"]))
                .order_by(Message.created_at)
            )
            if m.content
        ]
        result["runs"] = [
            run_view(r)
            for r in db.scalars(
                select(Run).where(Run.case_id == c.id).order_by(Run.created_at.desc()).limit(30)
            )
        ]
    return result


def run_view(r):
    return {
        "id": r.id,
        "kind": r.kind,
        "status": r.status,
        "revision": r.revision,
        "error": r.error,
        "created_at": r.created_at.isoformat(),
        "updated_at": r.updated_at.isoformat(),
        "result": r.result,
        "skill_hash": r.skill_hash,
        "model": r.model,
    }
