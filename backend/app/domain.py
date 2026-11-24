"""Pure, model-independent preflight rules. No database or network imports."""

import re
from datetime import date

from .schemas import Finding, Requirement


def norm(value):
    return re.sub(r"\s+", "", str(value))


def condition_value(condition, facts):
    if not isinstance(condition, dict):
        return None
    if not condition:
        return True
    if "all" in condition:
        values = [condition_value(c, facts) for c in condition["all"]]
        return False if False in values else (None if None in values else True)
    if "any" in condition:
        values = [condition_value(c, facts) for c in condition["any"]]
        return True if True in values else (None if None in values else False)
    field, op = condition.get("field"), condition.get("op", "eq")
    if field not in facts:
        return None
    actual, expected = facts[field], condition.get("value")
    if op == "eq":
        return actual == expected
    if op == "ne":
        return actual != expected
    if op == "in" and isinstance(expected, list):
        return actual in expected
    return None


def verify_evidence(evidence, documents, purpose=None):
    for e in evidence:
        e = e.model_dump() if hasattr(e, "model_dump") else e
        doc = next((d for d in documents if d["id"] == e["document_id"]), None)
        if not doc or (purpose and doc["purpose"] != purpose):
            raise ValueError("引用不属于本次检查的材料版本")
        page = next((p for p in doc["pages"] if p["number"] == e["page"]), None)
        if not page or norm(e["quote"]) not in norm(page["text"]):
            raise ValueError("引用片段无法在对应材料中定位")


def excerpts(doc, keyword=""):
    for p in doc["pages"]:
        text = p["text"]
        pos = text.find(keyword) if keyword else 0
        if pos >= 0 and text.strip():
            start = max(0, pos - 30)
            return [{"document_id": doc["id"], "page": p["number"], "quote": text[start : start + 300]}]
    return []


def candidates(requirement, documents):
    token = norm(requirement.document_type)
    material = [d for d in documents if d["purpose"] == "material"]
    types = requirement.parameters.get("document_types", [])
    if requirement.kind == "field_consistency" and isinstance(types, list) and types:
        return [
            d
            for d in material
            if any(
                norm(t) in norm(d.get("category", "")) or any(norm(t) in norm(p["text"]) for p in d["pages"])
                for t in types
                if str(t).strip()
            )
        ]
    if not token:
        return material
    return [
        d
        for d in material
        if token in norm(d.get("category", "")) or any(token in norm(p["text"]) for p in d["pages"])
    ]


def check_one(r, docs, facts, today=None):
    r = Requirement.model_validate(r)
    result = dict(
        requirement_id=r.id,
        applicability="applicable",
        verdict="unknown",
        method="deterministic",
        reason="需要结合材料内容进一步核对",
        next_action="核对原文或补充可读取材料",
        evidence=[],
        dependencies=["rules", "material_inventory", "facts"],
    )
    applicable = condition_value(r.condition, facts)
    if applicable is None:
        result.update(
            applicability="unknown", reason="适用条件尚未确认", next_action="请确认申请背景中的相关字段"
        )
        return Finding(**result).model_dump()
    if not applicable:
        result.update(applicability="not_applicable", reason="根据已确认背景，此项不适用", next_action="")
        return Finding(**result).model_dump()
    matched = candidates(r, docs)
    uncertain = [d for d in docs if d["purpose"] == "material" and d["parse_status"] != "ready"]
    readable = [d for d in matched if d["parse_status"] == "ready"]
    if not readable:
        if uncertain:
            result.update(
                reason="存在尚未完整读取的材料，暂不能确认是否缺件", next_action="先处理材料读取问题"
            )
        else:
            result.update(
                verdict="missing",
                reason=f"未找到可对应「{r.document_type or r.title}」的材料",
                next_action="上传对应材料，或检查材料分类和正文",
            )
        return Finding(**result).model_dump()
    evidence = [e for d in readable for e in excerpts(d, r.document_type)]
    result["evidence"] = evidence[:20]
    result["dependencies"] += [d["id"] for d in readable]
    p = r.parameters
    if r.kind == "manual_review":
        result.update(
            method="manual",
            reason="此项需要本人查看原件确认",
            next_action="检查签署、盖章或原件要求后记录人工确认",
        )
    elif r.kind == "material_presence":
        if evidence:
            result.update(
                verdict="pass", reason="已找到包含对应材料标识的可读文件；仅确认材料存在", next_action=""
            )
        else:
            result.update(reason="分类与要求匹配，但正文不足以确认材料类型")
    elif r.kind in ("file_format", "file_size", "page_count"):
        if r.kind == "file_format" and p.get("allowed"):
            ok = all(
                d["filename"].lower().rsplit(".", 1)[-1] in [a.lower().lstrip(".") for a in p["allowed"]]
                for d in readable
            )
            description = f"允许格式：{', '.join(p['allowed'])}"
        elif r.kind == "file_size" and isinstance(p.get("max_bytes"), (int, float)):
            ok = all(d["size"] <= p["max_bytes"] for d in readable)
            description = f"大小上限 {p['max_bytes']} 字节；实际 {[d['size'] for d in readable]}"
        elif r.kind == "page_count" and isinstance(p.get("max_pages"), int):
            if any(d["mime"] != "application/pdf" for d in readable):
                result.update(reason="非 PDF 材料无法按原版页数验证")
                return Finding(**result).model_dump()
            ok = all(len(d["pages"]) <= p["max_pages"] for d in readable)
            description = f"页数上限 {p['max_pages']}；实际 {[len(d['pages']) for d in readable]}"
        else:
            return Finding(**result).model_dump()
        result.update(
            verdict="pass" if ok else "fail",
            reason=description,
            next_action="" if ok else "按通知格式重新准备材料",
            evidence=[e for d in readable for e in excerpts(d)][:20],
        )
    elif r.kind in ("required_field", "field_consistency"):
        field = str(p.get("field", ""))
        values = []
        evidence = []
        if field:
            for d in readable:
                for page in d["pages"]:
                    matches = re.findall(re.escape(field) + r"\s*[：:]\s*([^\n\r;；]+)", page["text"])
                    for value in matches:
                        values.append(norm(value))
                        evidence += excerpts(d, field)
        if values:
            if r.kind == "field_consistency" and len(readable) < 2:
                result.update(reason="目前只有一份对应材料，无法完成跨材料一致性检查")
            elif len(set(values)) > 1 and r.kind == "field_consistency":
                result.update(
                    verdict="conflict",
                    reason=f"「{field}」出现不同值",
                    evidence=evidence[:20],
                    next_action="查看引用并确认应修改哪份材料",
                )
            elif r.kind == "required_field" or len(values) >= len(readable):
                result.update(
                    verdict="pass", reason=f"已读取并检查「{field}」", evidence=evidence[:20], next_action=""
                )
        else:
            result.update(reason=f"未能可靠读取「{field}」，不能据此认定材料缺失该字段")
    elif r.kind == "date_constraint":
        field, cutoff = str(p.get("field", "")), p.get("not_before", "")
        if not field or not cutoff:
            result.update(reason="日期规则缺少明确字段或比较日期")
        else:
            try:
                reference = date.fromisoformat(cutoff)
                values = []
                for d in readable:
                    for page in d["pages"]:
                        hits = re.findall(re.escape(field) + r"\s*[：:]\s*(\d{4}-\d{2}-\d{2})", page["text"])
                        values += [date.fromisoformat(v) for v in hits]
                if len(values) >= len(readable):
                    ok = all(v >= reference for v in values)
                    result.update(
                        verdict="pass" if ok else "fail",
                        reason=f"日期应不早于 {cutoff}（含当日）；读取到 {', '.join(map(str, values))}",
                        evidence=[e for d in readable for e in excerpts(d, field)][:20],
                        next_action="" if ok else "提供满足日期要求的材料",
                    )
            except (ValueError, TypeError):
                result.update(reason="日期格式或起算方式无法可靠解释")
    elif r.kind == "semantic_requirement":
        result.update(method="semantic", reason="需要逐段核对内容，目前尚未形成语义结论")
    return Finding(**result).model_dump()


def run_checks(snapshot):
    return [check_one(r, snapshot["documents"], snapshot["facts"]) for r in snapshot["requirements"]]


def overall(findings, stale=False, confirmed=None):
    if stale:
        return "stale"
    if not findings:
        return "not_ready"
    confirmed = set(confirmed or [])
    relevant = [f for f in findings if f["applicability"] != "not_applicable"]
    if any(f["verdict"] in ("missing", "fail", "conflict") for f in relevant):
        return "blocked"
    if any(
        f["applicability"] == "unknown"
        or (f["verdict"] == "unknown" and not (f["method"] == "manual" and f["requirement_id"] in confirmed))
        for f in relevant
    ):
        return "needs_review"
    return "ready"
