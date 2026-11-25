"""Synthetic sample. No real institution, applicant or application policy."""

import hashlib
from datetime import date, timedelta

from .domain import review_result, run_checks
from .models import Case, Document, RuleSet, Run
from .services import event, snapshot

NOTICE = """青禾大学 · 秋季交流项目（产品演示用虚构通知）
本示例只用于体验材料预检，不对应真实院校要求。
1. 必须提供申请表。
2. 必须提供成绩单。
3. 必须提供学习计划，说明学习目标与拟修课程。
4. 必须提供推荐信，推荐信须有推荐人签名。
5. 申请表与成绩单的姓名必须一致。
"""


def create_demo(db, owner_id):
    c = Case(
        owner_id=owner_id,
        title="秋季校际交流申请",
        institution="青禾大学 · 合成示例",
        deadline=(date.today() + timedelta(days=21)).isoformat(),
        revision=1,
        facts={"申请类别": "本科交流"},
    )
    db.add(c)
    db.flush()
    data = [
        ("交流项目申请通知", "source", "", NOTICE),
        ("申请表", "material", "申请表", "申请表\n姓名：林沐\n申请类别：本科交流\n目标院校：青禾大学\n"),
        ("成绩单", "material", "成绩单", "成绩单\n姓名：李沐\n学年：2025-2026\n平均绩点：3.6\n"),
    ]
    docs = []
    for title, purpose, category, text in data:
        d = Document(
            case_id=c.id,
            title=title,
            purpose=purpose,
            category=category,
            filename=title + ".txt",
            mime="text/plain",
            size=len(text.encode()),
            sha256=hashlib.sha256(text.encode()).hexdigest(),
            parse_status="ready",
            parse_method="synthetic",
            pages=[{"number": 1, "label": "全文", "text": text}],
        )
        db.add(d)
        docs.append(d)
    db.flush()
    definitions = [
        ("r1", "申请表", "material_presence", "申请表", "必须提供申请表。", {}),
        ("r2", "成绩单", "material_presence", "成绩单", "必须提供成绩单。", {}),
        (
            "r3",
            "学习计划内容",
            "semantic_requirement",
            "学习计划",
            "必须提供学习计划，说明学习目标与拟修课程。",
            {},
        ),
        ("r4", "推荐人签名", "manual_review", "推荐信", "必须提供推荐信，推荐信须有推荐人签名。", {}),
        (
            "r5",
            "姓名一致性",
            "field_consistency",
            "",
            "申请表与成绩单的姓名必须一致。",
            {"field": "姓名", "document_types": ["申请表", "成绩单"]},
        ),
    ]
    rules = [
        {
            "id": i,
            "title": title,
            "kind": kind,
            "document_type": doc_type,
            "required": True,
            "condition": {},
            "parameters": params,
            "source_evidence": [{"document_id": docs[0].id, "page": 1, "quote": q}],
            "explanation": "",
        }
        for i, title, kind, doc_type, q, params in definitions
    ]
    rs = RuleSet(case_id=c.id, version=1, status="active", requirements=rules, source_ids=[docs[0].id])
    db.add(rs)
    db.flush()
    c.active_rules_id = rs.id
    snap = snapshot(db, c)
    run = Run(
        case_id=c.id,
        kind="check",
        status="completed",
        revision=c.revision,
        snapshot=snap,
        result={
            **review_result(snap, run_checks(snap)),
            "answer": "这是合成示例的确定性检查结果。点击「重新预检」可运行真实 Agent。",
        },
    )
    db.add(run)
    db.flush()
    c.current_check_id = run.id
    event(db, run.id, "run.completed", {"synthetic": True})
    return c
