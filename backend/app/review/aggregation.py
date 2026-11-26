"""Result coverage, freshness metadata and conservative readiness aggregation."""

import hashlib
import json
from collections import Counter

from pydantic import ValidationError

from ..schemas import Finding, Requirement
from .conditions import condition_value
from .version import REVIEW_ENGINE_VERSION


def requirements_fingerprint(requirements):
    return hashlib.sha256(
        json.dumps(requirements, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def assess_results(requirements, findings, facts, *, stale=False, confirmed=None):
    """Aggregate against the expected rule set, not just whichever rows happened to be saved."""
    expected = {}
    invalid_rule_ids = []
    for raw in requirements:
        try:
            rule = Requirement.model_validate(raw)
            if rule.id in expected:
                invalid_rule_ids.append(rule.id)
            expected[rule.id] = rule
        except (ValidationError, TypeError):
            invalid_rule_ids.append(str(raw.get("id", "?")) if isinstance(raw, dict) else "?")
    rows = {}
    unexpected_ids, invalid_ids = [], []
    counts = Counter()
    for raw in findings:
        identifier = raw.get("requirement_id") if isinstance(raw, dict) else None
        if not isinstance(identifier, str):
            invalid_ids.append("?")
            continue
        counts[identifier] += 1
        if identifier not in expected:
            unexpected_ids.append(identifier)
            continue
        try:
            f = Finding.model_validate(raw).model_dump()
            r = expected[identifier]
            applies = condition_value(r.condition, facts)
            applicability = "unknown" if applies is None else "applicable" if applies else "not_applicable"
            if f["applicability"] != applicability:
                raise ValueError("applicability mismatch")
            if applicability != "applicable" and f["verdict"] != "unknown":
                raise ValueError("unsupported verdict without applicability")
            if f["method"] == "manual" and r.kind != "manual_review":
                raise ValueError("manual method cannot bypass a rule")
            if r.kind not in ("semantic_requirement", "manual_review") and f["method"] != "deterministic":
                raise ValueError("wrong verification method")
            if f["verdict"] == "pass":
                if r.kind == "manual_review" or not f["evidence"]:
                    raise ValueError("unsupported pass")
                if r.kind == "material_presence" and not any(
                    m["status"] == "verified" for m in f["material_matches"]
                ):
                    raise ValueError("missing material confirmation")
                if r.kind in ("field_consistency", "required_field", "date_constraint"):
                    coverage = f["field_coverage"]
                    ids = [c["document_id"] for c in coverage]
                    if (
                        not coverage
                        or len(ids) != len(set(ids))
                        or any(c["status"] != "covered" for c in coverage)
                    ):
                        raise ValueError("incomplete document coverage")
            rows[identifier] = f
        except (ValidationError, TypeError, ValueError):
            invalid_ids.append(identifier)
    duplicates = [identifier for identifier, count in counts.items() if count > 1]
    missing = [identifier for identifier in expected if not counts[identifier]]
    safe = []
    for identifier, r in expected.items():
        if identifier in duplicates or identifier in invalid_ids or identifier not in rows:
            state = "not_evaluated" if identifier in missing else "invalid"
            f = Finding(
                requirement_id=identifier,
                applicability="unknown",
                verdict="unknown",
                reason="本项尚未形成检查结果"
                if state == "not_evaluated"
                else "本项检查结果重复或不符合当前规则",
                next_action="请重新预检，补齐当前要求的有效结果",
            ).model_dump()
        else:
            f = rows[identifier]
            state = "evaluated"
        safe.append({**f, "evaluation_state": state})
    coverage = {
        "expected_count": len(expected),
        "evaluated_count": sum(f["evaluation_state"] == "evaluated" for f in safe),
        "missing_ids": missing,
        "duplicate_ids": sorted(set(duplicates)),
        "unexpected_ids": sorted(set(unexpected_ids)),
        "invalid_ids": sorted(set(invalid_ids)),
        "invalid_rule_ids": sorted(set(invalid_rule_ids)),
    }
    coverage["complete"] = bool(expected) and not any(
        coverage[k]
        for k in ("missing_ids", "duplicate_ids", "unexpected_ids", "invalid_ids", "invalid_rule_ids")
    )
    confirmed = set(confirmed or [])
    relevant = [
        f for f in safe if expected[f["requirement_id"]].required and f["applicability"] != "not_applicable"
    ]
    advisory_count = sum(
        not expected[f["requirement_id"]].required
        and f["applicability"] != "not_applicable"
        and f["verdict"] != "pass"
        for f in safe
    )
    if stale:
        status = "stale"
    elif not requirements:
        status = "not_ready"
    elif not coverage["complete"]:
        status = "needs_review"
    elif any(f["verdict"] in ("missing", "fail", "conflict") for f in relevant):
        status = "blocked"
    elif any(
        f["applicability"] == "unknown"
        or (f["verdict"] == "unknown" and not (f["method"] == "manual" and f["requirement_id"] in confirmed))
        for f in relevant
    ):
        status = "needs_review"
    else:
        status = "ready"
    return {"status": status, "coverage": coverage, "findings": safe, "advisory_count": advisory_count}


def review_result(snapshot, findings):
    return {
        "engine_version": REVIEW_ENGINE_VERSION,
        "rules_id": snapshot.get("rules_id"),
        "requirements_fingerprint": requirements_fingerprint(snapshot["requirements"]),
        "findings": findings,
        "coverage": assess_results(snapshot["requirements"], findings, snapshot["facts"])["coverage"],
    }


def overall(findings, stale=False, confirmed=None, *, requirements=None, facts=None):
    if stale:
        return "stale"
    if requirements is None:
        return "not_ready"
    return assess_results(requirements, findings, facts or {}, confirmed=confirmed)["status"]
