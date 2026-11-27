"""Immutable job inputs, idempotent enqueueing and run ownership."""

import hashlib
import json
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import select

from ..db import now
from ..models import Message, RuleSet, Run, RunEvent, WorkItem
from ..review.structure import source_versions_valid
from .cases import case_for, expect_revision
from .documents import doc_view, documents_for
from .subjects import case_subjects, require_scenario_subject


def snapshot(db, case):
    rules = db.get(RuleSet, case.active_rules_id) if case.active_rules_id else None
    docs = documents_for(db, case.id)
    valid_rules = bool(rules and source_versions_valid(rules, docs))
    return {
        "case_id": case.id,
        "workspace_id": case.workspace_id,
        "subjects": case_subjects(db, case),
        "work_plan": [
            {"id": w.id, "kind": w.kind, "title": w.title, "status": w.status, "detail": w.detail}
            for w in db.scalars(select(WorkItem).where(WorkItem.case_id == case.id))
        ],
        "title": case.title,
        "scenario": case.scenario_snapshot,
        "revision": case.revision,
        "deadline": case.deadline,
        "reference_date": now().astimezone(ZoneInfo(case.timezone)).date().isoformat(),
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
    from sqlalchemy import func

    from ..models import Case

    pending = db.scalar(
        select(func.count())
        .select_from(Run)
        .join(Case, Case.id == Run.case_id)
        .where(Case.owner_id == case.owner_id, Run.status.in_(["queued", "running"]))
    )
    if pending >= 10:
        raise HTTPException(429, "待处理任务已达 10 个，请等待完成或取消后重试")
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


def run_for(db, user, run_id):
    r = db.get(Run, run_id)
    if not r:
        raise HTTPException(404, "运行不存在")
    case_for(db, user.id, r.case_id)
    return r


def start_run(db, user, case_id, kind, revision, payload, key):
    c = case_for(db, user.id, case_id, True)
    # Idempotent replays must work even if an earlier request changed the revision later.
    if key:
        prior = db.scalar(select(Run).where(Run.case_id == c.id, Run.idempotency_key == key))
        if prior:
            r, _ = enqueue(db, c, kind, payload, key)
            return run_view(r)
    expect_revision(c, revision)
    if kind == "check" and not c.active_rules_id:
        raise HTTPException(422, "请先启用一版申请要求")
    if kind == "check":
        require_scenario_subject(db, c)
        if not snapshot(db, c)["requirements"]:
            raise HTTPException(409, "通知来源已变化，请重新提取并启用要求")
    if kind == "extract" and not any(
        d.purpose == "source" and d.parse_status == "ready" for d in documents_for(db, c.id)
    ):
        raise HTTPException(422, "请先导入可读取的申请通知")
    running = db.scalar(
        select(Run).where(Run.case_id == c.id, Run.kind != "parse", Run.status.in_(["queued", "running"]))
    )
    if running:
        raise HTTPException(409, "当前事项已有分析任务，请等待完成或取消")
    r, created = enqueue(db, c, kind, payload, key)
    if created and payload.get("text"):
        db.add(Message(case_id=c.id, run_id=r.id, role="user", content=payload["text"]))
    db.commit()
    return run_view(r)
