"""Bounded requirement trees, source conflicts and explicit material scope."""

from datetime import date

from ..schemas import Requirement
from .common import norm


def child_ids(requirements):
    return {
        child
        for r in requirements
        if r["kind"] == "group"
        for child in r.get("parameters", {}).get("children", [])
    }


def validate_structure(requirements):
    rules = {r["id"]: Requirement.model_validate(r) for r in requirements}
    if len(rules) != len(requirements):
        raise ValueError("要求标识不能重复")
    owners = {}
    for rule in rules.values():
        validate_condition(rule.condition)
        p = rule.parameters
        if p.get("severity", "blocking") not in ("blocking", "warning", "info"):
            raise ValueError("严重程度无效")
        for name in ("min_count", "max_count"):
            if name in p and (type(p[name]) is not int or not 1 <= p[name] <= 30):
                raise ValueError("数量必须为 1～30 的整数")
        if p.get("min_count", 1) > p.get("max_count", 30):
            raise ValueError("最少数量不能大于最多数量")
        if p.get("distinct_by", "original") not in ("original", "issuer", "document"):
            raise ValueError("独立性规则无效")
        if p.get("variant", "") not in ("", "original", "translation"):
            raise ValueError("材料形式无效")
        for key in ("not_before", "not_after", "source_valid_until"):
            if p.get(key):
                try:
                    date.fromisoformat(p[key])
                except (TypeError, ValueError) as error:
                    raise ValueError("日期应为 YYYY-MM-DD") from error
        if p.get("reference", "") not in ("", "deadline", "today"):
            raise ValueError("日期参照无效")
        for key in ("offset_days", "max_age_days"):
            if key in p and (type(p[key]) is not int or not -36500 <= p[key] <= 36500):
                raise ValueError("日期天数参数无效")
        if p.get("max_age_days", 0) < 0:
            raise ValueError("有效天数不能为负")
        criteria = p.get("criteria", [])
        if (
            not isinstance(criteria, list)
            or len(criteria) > 20
            or any(not isinstance(v, str) or not v.strip() or len(v) > 300 for v in criteria)
            or len(criteria) != len(set(criteria))
        ):
            raise ValueError("语义检查点须为互不重复的非空文本，最多 20 项")
        if rule.kind == "group":
            children = p.get("children", [])
            if (
                not isinstance(children, list)
                or not 1 <= len(children) <= 30
                or len(set(children)) != len(children)
            ):
                raise ValueError("要求组需有 1～30 个不同子项")
            if p.get("operator", "all") not in ("all", "any", "at_least"):
                raise ValueError("要求组操作无效")
            if p.get("operator") == "at_least" and p.get("min_count", 1) > len(children):
                raise ValueError("组内最少通过数超过子项数量")
            for child in children:
                if child not in rules or child == rule.id or child in owners:
                    raise ValueError("子要求不存在、重复归属或引用了自身")
                owners[child] = rule.id
    for identifier in rules:
        seen = set()
        node = identifier
        while node in owners:
            if node in seen or len(seen) > 8:
                raise ValueError("要求树存在循环或超过 8 层")
            seen.add(node)
            node = owners[node]


def validate_condition(condition, depth=0):
    if not isinstance(condition, dict) or depth > 8:
        raise ValueError("条件结构无效或超过 8 层")
    if not condition:
        return
    if "all" in condition or "any" in condition:
        op = "all" if "all" in condition else "any"
        values = condition[op]
        if set(condition) != {op} or not isinstance(values, list) or not 1 <= len(values) <= 30:
            raise ValueError("条件组需有 1～30 个子条件")
        for value in values:
            validate_condition(value, depth + 1)
    elif (
        not isinstance(condition.get("field"), str)
        or not condition["field"].strip()
        or condition.get("op", "eq") not in ("eq", "ne", "in")
        or "value" not in condition
    ):
        raise ValueError("条件须指定背景字段、有效比较方式和值")
    elif condition.get("op") == "in" and (not isinstance(condition["value"], list) or not condition["value"]):
        raise ValueError("属于条件需要非空比较值列表")


def source_conflicts(requirements):
    conflicts = []
    for index, r in enumerate(requirements):
        if r["kind"] == "group":
            continue
        for other in requirements[:index]:
            def scope(x):
                return (
                            x["kind"],
                            x["document_type"],
                            x.get("parameters", {}).get("slot_id"),
                            x.get("parameters", {}).get("subject_role"),
                            x.get("parameters", {}).get("field"),
                            str(x.get("condition", {})),
                        )
            def ids(x):
                return {e["document_id"] for e in x["source_evidence"]}
            def trim(x):
                return {
                            k: v
                            for k, v in x.get("parameters", {}).items()
                            if k not in ("conflict_resolution", "source_valid_until")
                        }
            if scope(r) == scope(other) and ids(r) != ids(other) and trim(r) != trim(other):
                conflicts.append(
                    {
                        "requirements": [other["id"], r["id"]],
                        "message": "不同通知对同一材料范围给出不同参数，请比较原文并选用或说明并行适用原因",
                        "resolved": bool(
                            r["parameters"].get("conflict_resolution")
                            and other["parameters"].get("conflict_resolution")
                        ),
                    }
                )
    return conflicts


def source_versions_valid(rules, docs):
    by_id = {d.id: d for d in docs if d.purpose == "source" and d.parse_status == "ready"}
    return set(rules.source_ids).issubset(by_id) and all(
        identifier in by_id and by_id[identifier].current_parse_id == version
        for identifier, version in (rules.source_versions or {}).items()
    )


def scoped_documents(rule, docs, subjects):
    p = rule.parameters
    subject_id = p.get("subject_id")
    if p.get("subject_role"):
        ids = {s["subject_id"] for s in subjects if s["role"] == p["subject_role"] and not s.get("archived")}
        if subject_id and subject_id not in ids or not subject_id and len(ids) != 1:
            return [], "角色主体缺失或不唯一，请明确本项的主体"
        subject_id = subject_id or next(iter(ids))
    if subject_id and not any(s["subject_id"] == subject_id and not s.get("archived") for s in subjects):
        return [], "指定主体未关联当前事项"
    result = []
    for doc in docs:
        a = doc.get("assignment", {})
        if a.get("state") == "rejected":
            continue
        if subject_id and (a.get("state") != "accepted" or a.get("subject_id") != subject_id):
            continue
        if p.get("slot_id") and (a.get("state") != "accepted" or p["slot_id"] not in a.get("slot_ids", [])):
            continue
        if p.get("variant") and a.get("variant") != p["variant"]:
            continue
        result.append(doc)
    return result, "" if result or not (
        subject_id or p.get("slot_id") or p.get("variant")
    ) else "尚无已确认属于该主体/槽位的材料"


def accepted_identity(doc, document_type):
    a = doc.get("assignment", {})
    if a.get("state") != "accepted" or norm(a.get("document_type", "")) != norm(document_type):
        return None
    if doc["parse_status"] != "ready" or not doc["pages"]:
        return None
    heading = "\n".join(p["text"] for p in doc["pages"])[:500]
    if any(marker in heading for marker in ("填写说明", "空白模板", "填写示例", "待填写", "________")):
        return None
    from .evidence import excerpts

    evidence = excerpts(doc)
    if not evidence:
        return None
    return {
        "document_id": doc["id"],
        "status": "verified",
        "reason": "用户确认材料类型与范围；不代表真实性或全部内容合格",
        "evidence": evidence,
    }
