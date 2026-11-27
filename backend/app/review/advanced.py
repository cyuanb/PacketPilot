"""Tree evaluation, quantity independence, subject scope and explicit date windows."""

from datetime import date, timedelta

from ..schemas import Finding, Requirement
from .checks import check_one
from .conditions import condition_value
from .evidence import excerpts
from .fields import field_coverage
from .matching import candidates, material_identity
from .structure import scoped_documents, validate_structure


def unknown(rule, reason):
    return Finding(
        requirement_id=rule.id, verdict="unknown", reason=reason, next_action="确认范围或补充材料后复检"
    ).model_dump()


def evaluate_leaf(raw, snapshot):
    rule = Requirement.model_validate(raw)
    p = rule.parameters
    docs, scope_error = scoped_documents(rule, snapshot["documents"], snapshot.get("subjects", []))
    if condition_value(rule.condition, snapshot["facts"]) is not True:
        return check_one(raw, docs, snapshot["facts"])
    reference = date.fromisoformat(snapshot.get("reference_date") or date.today().isoformat())
    if p.get("source_valid_until") and reference > date.fromisoformat(p["source_valid_until"]):
        return unknown(rule, "本项通知或模板的有效日期已过，请确认当前接收规则")
    if scope_error:
        return unknown(rule, scope_error)
    result = check_one(raw, docs, snapshot["facts"])
    matched = candidates(rule, docs)
    if rule.kind == "material_presence" and any(
        k in p for k in ("min_count", "max_count", "distinct_by", "requires_pair")
    ):
        matches = [material_identity(d, rule.document_type) for d in matched]
        verified = {m["document_id"] for m in matches if m["status"] == "verified"}
        usable = [d for d in matched if d["id"] in verified]
        distinct_by = p.get("distinct_by", "original")
        if distinct_by == "issuer" and any(not d.get("assignment", {}).get("issuer") for d in usable):
            return unknown(rule, "独立出具方未明确，不能按文件份数推断独立证明数量")
        keys = [
            d.get("assignment", {}).get("issuer")
            if distinct_by == "issuer"
            else (d.get("sha256") or d["id"])
            if distinct_by == "original"
            else d.get("logical_id", d["id"])
            for d in usable
        ]
        count = len(set(keys))
        minimum, maximum = p.get("min_count", 1), p.get("max_count", 30)
        result.update(
            material_matches=matches,
            evidence=[e for m in matches if m["status"] == "verified" for e in m["evidence"]][:20],
        )
        if count > maximum:
            result.update(
                verdict="fail",
                reason=f"独立材料 {count} 份，超过最多 {maximum} 份",
                next_action="核对所需版本和数量",
            )
        elif count < minimum:
            uncertain = any(m["status"] != "verified" for m in matches) or any(
                d["purpose"] == "material" and d["parse_status"] != "ready" for d in docs
            )
            result.update(
                verdict="unknown" if uncertain else "missing",
                reason=f"可确认的独立材料 {count} 份，需要至少 {minimum} 份",
                next_action="补齐材料或确认候选、独立出具方",
            )
        else:
            result.update(
                verdict="pass",
                reason=f"独立材料数量 {count}，满足 {minimum}～{maximum} 份要求",
                next_action="",
            )
        if p.get("requires_pair") and result["verdict"] == "pass":
            for doc in usable:
                a = doc.get("assignment", {})
                counterpart = "translation" if a.get("variant") == "original" else "original"
                pairs = [
                    d
                    for d in snapshot["documents"]
                    if d["purpose"] == "material"
                    and d["id"] != doc["id"]
                    and d.get("assignment", {}).get("state") == "accepted"
                    and a.get("pair_key")
                    and d["assignment"].get("pair_key") == a["pair_key"]
                    and d["assignment"].get("variant") == counterpart
                    and d["assignment"].get("subject_id") == a.get("subject_id")
                    and d["parse_status"] == "ready"
                ]
                if not pairs:
                    result.update(
                        verdict="unknown",
                        reason="原件/译件未建立同主体的明确配对",
                        next_action="确认原件与译件配对标识并检查读取状态",
                    )
                    break
                result["evidence"] = (result["evidence"] + [e for d in pairs for e in excerpts(d)])[:20]
    if rule.kind == "date_constraint" and any(
        k in p for k in ("not_after", "reference", "max_age_days", "end_field")
    ):
        coverage = field_coverage(matched, p.get("field", ""), dates=True)
        result["field_coverage"] = coverage
        result["evidence"] = [e for c in coverage for e in c["evidence"]][:20]
        if not coverage or any(c["status"] != "covered" for c in coverage):
            result.update(
                verdict="unknown", reason="日期在各材料中缺失、歧义或无法读取", next_action="逐份核对日期"
            )
        else:
            try:
                ref = (
                    date.fromisoformat(snapshot["deadline"])
                    if p.get("reference") == "deadline"
                    else reference
                )
                ref += timedelta(days=p.get("offset_days", 0))
                lower = date.fromisoformat(p["not_before"]) if p.get("not_before") else None
                upper = date.fromisoformat(p["not_after"]) if p.get("not_after") else None
                if p.get("reference") and not p.get("end_field"):
                    lower = lower or ref
                if "max_age_days" in p:
                    lower, upper = ref - timedelta(days=p["max_age_days"]), ref
                values = [date.fromisoformat(c["values"][0]) for c in coverage]
                ok = all(
                    (lower is None or value >= lower) and (upper is None or value <= upper)
                    for value in values
                )
                if p.get("end_field"):
                    ends = field_coverage(matched, p["end_field"], dates=True)
                    if any(c["status"] != "covered" for c in ends) or len(ends) != len(coverage):
                        raise ValueError("period incomplete")
                    ok = ok and all(
                        start <= ref <= date.fromisoformat(end["values"][0])
                        for start, end in zip(values, ends)
                    )
                    result["evidence"] = (result["evidence"] + [e for c in ends for e in c["evidence"]])[:20]
                result.update(
                    verdict="pass" if ok else "fail",
                    reason=f"日期区间核验，参照 {ref}，下界 {lower or '无'}，上界 {upper or '无'}（含边界）",
                    next_action="" if ok else "提供满足日期或有效期间的材料",
                )
            except (ValueError, KeyError, TypeError):
                result.update(
                    verdict="unknown",
                    reason="参照日期或有效期间无法明确解释",
                    next_action="确认截止日期与起止字段",
                )
    return Finding.model_validate(result).model_dump()


def evaluate_rules(snapshot, overrides=None):
    requirements = snapshot["requirements"]
    validate_structure(requirements)
    rules = {r["id"]: r for r in requirements}
    results = {}

    def evaluate(identifier):
        if identifier in results:
            return results[identifier]
        raw = rules[identifier]
        rule = Requirement.model_validate(raw)
        if rule.kind != "group":
            result = (
                overrides[identifier]
                if overrides and identifier in overrides
                else evaluate_leaf(raw, snapshot)
            )
        elif condition_value(rule.condition, snapshot["facts"]) is not True:
            result = check_one(raw, snapshot["documents"], snapshot["facts"])
        else:
            p = rule.parameters
            children = [evaluate(child) for child in p["children"]]
            active = [c for c in children if c["applicability"] != "not_applicable"]
            passed = sum(c["verdict"] == "pass" for c in active)
            uncertain = sum(c["verdict"] == "unknown" for c in active)
            need = (
                len(active)
                if p.get("operator", "all") == "all"
                else 1
                if p["operator"] == "any"
                else p.get("min_count", 1)
            )
            verdict = (
                "pass"
                if active and passed >= need
                else "unknown"
                if not active or passed + uncertain >= need
                else "fail"
            )
            result = Finding(
                requirement_id=identifier,
                verdict=verdict,
                reason=f"要求组：{passed}/{len(active)} 项已通过，需要 {need} 项；人工确认在子项中保留",
                next_action="" if verdict == "pass" else "查看组内未决子要求",
                evidence=[e for c in active if c["verdict"] == "pass" for e in c["evidence"]][:20],
                dependencies=p["children"],
            ).model_dump()
        # Evidence always references the exact parser projection used by this run.
        all_evidence = (
            result["evidence"]
            + [e for c in result.get("field_coverage", []) for e in c["evidence"]]
            + [e for m in result.get("material_matches", []) for e in m["evidence"]]
        )
        for e in all_evidence:
            doc = next((d for d in snapshot["documents"] if d["id"] == e["document_id"]), None)
            if doc:
                e["parse_revision_id"] = doc.get("parse_revision_id")
        results[identifier] = result
        return result

    return [evaluate(r["id"]) for r in requirements]
