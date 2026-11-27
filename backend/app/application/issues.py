"""Amendment progress is separate from check verdicts; only current evidence resolves issues."""

import hashlib
import json

from fastapi import HTTPException
from sqlalchemy import select

from ..db import now
from ..models import Issue, IssueEvent
from ..review.structure import child_ids
from .reports import checklist


def issue_event(db, issue, action, note=""):
    db.add(
        IssueEvent(
            issue_id=issue.id,
            action=action,
            note=note,
            case_revision=issue.checked_revision,
            run_id=issue.run_id,
        )
    )


def synchronize_issues(db, case):
    report = checklist(db, case)
    if not report["can_export"]:
        raise HTTPException(409, "请先完成当前版本的完整检查；旧或不完整结果不能关闭问题")
    existing = {
        issue.requirement_id: issue
        for issue in db.scalars(select(Issue).where(Issue.case_id == case.id).with_for_update())
    }
    requirements = {rule["id"]: rule for rule in report["requirements"]}
    children = child_ids(report["requirements"])
    confirmed = {entry["requirement_id"] for entry in report["attestations"]}
    for finding in report["findings"]:
        key = finding["requirement_id"]
        rule = requirements[key]
        required = (
            rule["required"]
            and key not in children
            and rule.get("parameters", {}).get("severity", "blocking") == "blocking"
        )
        fingerprint = hashlib.sha256(
            json.dumps(rule, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()
        resolved = (
            finding["applicability"] == "not_applicable"
            or finding["verdict"] == "pass"
            or finding.get("satisfied_by_confirmation", False)
            or (
                finding["method"] == "manual"
                and key in confirmed
                and finding["applicability"] == "applicable"
            )
        )
        issue = existing.get(key)
        if issue is None:
            if resolved:
                continue
            issue = Issue(
                case_id=case.id,
                requirement_id=key,
                rule_fingerprint=fingerprint,
                title=rule["title"],
                required=required,
                verdict=finding["verdict"],
                reason=finding["reason"],
                next_action=finding["next_action"],
                run_id=report["run_id"],
                checked_revision=case.revision,
                status="open",
            )
            db.add(issue)
            db.flush()
            issue_event(db, issue, "opened")
            continue
        same_basis = (
            issue.run_id == report["run_id"]
            and issue.checked_revision == case.revision
            and issue.rule_fingerprint == fingerprint
        )
        status = (
            "resolved"
            if resolved
            else issue.status
            if same_basis and issue.status in {"open", "requested", "submitted", "exception"}
            else "requested"
            if issue.status == "requested" and issue.rule_fingerprint == fingerprint
            else "open"
        )
        reason = (
            "本人已确认当前版本的人工检查项；不等同于机器验证通过。"
            if resolved and finding["method"] == "manual" and key in confirmed
            else finding["reason"]
        )
        next_action = "" if resolved else finding["next_action"]
        changed = (
            not same_basis
            or issue.status != status
            or issue.reason != reason
            or issue.next_action != next_action
        )
        old_status = issue.status
        issue.rule_fingerprint, issue.title, issue.required = fingerprint, rule["title"], required
        issue.verdict, issue.reason, issue.next_action = (
            finding["verdict"],
            reason,
            next_action,
        )
        issue.run_id, issue.checked_revision, issue.status = report["run_id"], case.revision, status
        if changed:
            issue.revision += 1
            issue.updated_at = now()
            if not same_basis:
                issue.note = ""
            issue_event(
                db,
                issue,
                "resolved"
                if status == "resolved"
                else "reopened"
                if old_status in {"resolved", "submitted", "exception", "retired"} and status == "open"
                else "rechecked",
            )
    for key, issue in existing.items():
        if key not in requirements and issue.status != "retired":
            issue.status = "retired"
            issue.checked_revision, issue.run_id = case.revision, report["run_id"]
            issue.revision += 1
            issue.updated_at = now()
            issue_event(db, issue, "requirement_removed")
    db.flush()


def issues_view(db, case):
    report = checklist(db, case)
    rows = db.scalars(
        select(Issue).where(Issue.case_id == case.id).order_by(Issue.created_at, Issue.id)
    ).all()
    return {
        "can_sync": report["can_export"],
        "items": [
            {
                "id": issue.id,
                "requirement_id": issue.requirement_id,
                "title": issue.title,
                "required": issue.required,
                "status": issue.status,
                "verdict": issue.verdict,
                "reason": issue.reason,
                "next_action": issue.next_action,
                "revision": issue.revision,
                "checked_revision": issue.checked_revision,
                "run_id": issue.run_id,
                "note": issue.note,
                "stale": not report["can_export"]
                or case.revision != issue.checked_revision
                or report["run_id"] != issue.run_id,
                "updated_at": issue.updated_at.isoformat(),
            }
            for issue in rows
        ],
    }


def set_issue_status(db, case, issue, status, note, revision):
    if issue.revision != revision:
        raise HTTPException(409, "问题状态已变化，请刷新后重试")
    if issue.status in {"resolved", "retired"}:
        raise HTTPException(409, "此问题已关闭；输入变化后请复检，不可手工改写检查结论")
    if status == "exception":
        report = checklist(db, case)
        if (
            not report["can_export"]
            or issue.run_id != report["run_id"]
            or issue.checked_revision != case.revision
        ):
            raise HTTPException(409, "例外说明必须绑定当前有效检查，请先复检并同步")
        if not note.strip():
            raise HTTPException(422, "请填写例外说明；例外不等于检查通过")
    issue.status, issue.note = status, note.strip()
    issue.revision += 1
    issue.updated_at = now()
    db.add(
        IssueEvent(
            issue_id=issue.id,
            action="user." + status,
            note=issue.note,
            case_revision=case.revision,
            run_id=issue.run_id,
        )
    )
