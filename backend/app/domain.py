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


def is_placeholder(value):
    return (
        not value
        or bool(re.fullmatch(r"[_\-—.\s]+", value))
        or value in {"待填写", "请填写", "未填写", "待补充", "N/A", "n/a", "TODO"}
        or value.startswith(("请填写", "请填入", "待填写", "待补充"))
        or bool(re.fullmatch(r"\{\{.*\}\}|\[.*\]|[（(](?:请)?填写.*[）)]", value))
    )


def field_coverage(documents, field, *, dates=False):
    """Extract each document independently; a repeated value never covers another document."""
    coverage = []
    pattern = re.compile(
        r"(?:^|[;；|])[ \t]*" + re.escape(field) + r"[ \t]*[：:][ \t]*([^\r\n;；|]*)", re.MULTILINE
    )
    for doc in documents:
        item = {
            "document_id": doc["id"],
            "field": field,
            "status": "unreadable",
            "values": [],
            "evidence": [],
        }
        if doc["parse_status"] == "ready":
            invalid = False
            for page in doc["pages"]:
                for match in pattern.finditer(page["text"]):
                    raw = match.group(1).strip()
                    if is_placeholder(raw):
                        continue
                    if len(raw) > 1000:
                        invalid = True
                        continue
                    value = raw if dates else norm(raw)
                    if value not in item["values"]:
                        item["values"].append(value)
                        item["evidence"].append(
                            {
                                "document_id": doc["id"],
                                "page": page["number"],
                                "quote": match.group(0).strip()[:1000],
                            }
                        )
            if dates:
                for value in item["values"]:
                    try:
                        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                            raise ValueError("ambiguous date")
                        date.fromisoformat(value)
                    except ValueError:
                        invalid = True
            item["status"] = (
                "invalid"
                if invalid
                else "missing"
                if not item["values"]
                else "ambiguous"
                if len(item["values"]) > 1
                else "covered"
            )
        coverage.append(item)
    return coverage


# Deliberately limited structure checks, not a general classifier or authenticity detector.
# Each group requires one non-placeholder field, in addition to a document heading.
MATERIAL_PROFILES = {
    "成绩单": (("姓名", "学生姓名"), ("平均绩点", "绩点", "成绩", "课程成绩")),
    "申请表": (("姓名", "申请人"), ("申请类别", "目标院校", "申请项目")),
    "学习计划": (("学习目标",), ("拟修课程", "学习安排")),
    "推荐信": (("姓名", "申请人"), ("推荐意见",)),
    "入职登记表": (("姓名",), ("入职日期", "部门", "岗位")),
    "营业执照": (("名称", "企业名称"), ("统一社会信用代码", "注册号")),
}


def material_identity(document, document_type):
    result = {"document_id": document["id"], "status": "unverified", "reason": "", "evidence": []}
    if document["parse_status"] != "ready":
        return {**result, "status": "unreadable", "reason": "材料内容尚未完整读取"}
    first = next(
        ((page, line) for page in document["pages"] for line in page["text"].splitlines() if line.strip()),
        None,
    )
    profile = MATERIAL_PROFILES.get(document_type)
    if not first or not profile:
        return {**result, "reason": "当前没有足够的材料类型结构证据，需要后续匹配或人工核对"}
    page, line = first
    heading = norm(line.strip().lstrip("#").strip())
    expected = re.escape(document_type) + r"(?:[（(](?:合成演示材料|合成示例|合成材料|synthetic)[）)])?"
    if not re.fullmatch(expected, heading):
        return {**result, "reason": "正文提及或标签匹配不足以确认材料类型；未找到明确的材料标题"}
    first_lines = "\n".join(p["text"] for p in document["pages"]).splitlines()[:4]
    if any(re.search(r"填写说明|填写示例|样例|模板", line) for line in first_lines):
        return {**result, "reason": "文件带有说明或模板标记，不能直接当作已完成材料"}
    evidence = [{"document_id": document["id"], "page": page["number"], "quote": line.strip()[:300]}]
    for alternatives in profile:
        field = next(
            (
                c
                for name in alternatives
                for c in field_coverage([document], name)
                if c["status"] == "covered"
            ),
            None,
        )
        if field is None:
            return {**result, "reason": "有材料标题，但结构字段不足或仍有占位内容，需要核对原件"}
        evidence.extend(field["evidence"])
    return {
        **result,
        "status": "verified",
        "reason": "材料标题与有限结构字段相互支持；不验证真实性",
        "evidence": evidence,
    }


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
    if r.kind == "material_presence":
        result["material_matches"] = [material_identity(d, r.document_type) for d in matched]
    field = r.parameters.get("field")
    if (
        r.kind in ("required_field", "field_consistency", "date_constraint")
        and isinstance(field, str)
        and field
    ):
        result["field_coverage"] = field_coverage(matched, field, dates=r.kind == "date_constraint")
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
        verified = [m for m in result["material_matches"] if m["status"] == "verified"]
        if verified:
            result.update(
                verdict="pass",
                reason="已找到标题与结构字段匹配的可读材料；不代表内容全部合格或真实性已验证",
                evidence=[e for m in verified for e in m["evidence"]][:20],
                next_action="",
            )
        else:
            result.update(
                reason="仅找到候选内容，材料类型或填写完整性尚未确认",
                evidence=[],
                next_action="查看候选说明，提供可识别的完整材料；不能只凭文件名或提及词判定",
            )
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
        coverage = result.get("field_coverage", [])
        result["evidence"] = [e for c in coverage for e in c["evidence"]][:20]
        if not coverage:
            result.update(reason="字段规则缺少明确的字段标签")
        elif any(c["status"] != "covered" for c in coverage):
            result.update(
                reason=f"并非每份对应材料都能唯一读取「{field}」；请逐份确认",
                next_action="查看逐材料覆盖，补充缺失内容或确认多值的主体",
            )
        elif r.kind == "field_consistency" and len(coverage) < 2:
            result.update(reason="目前只有一份对应材料，无法完成跨材料一致性检查")
        elif r.kind == "field_consistency" and len({c["values"][0] for c in coverage}) > 1:
            result.update(
                verdict="conflict",
                reason=f"「{field}」出现不同值",
                next_action="查看各份材料的字段引用并确认应修改哪份",
            )
        else:
            result.update(verdict="pass", reason=f"已逐份读取并检查「{field}」", next_action="")
    elif r.kind == "date_constraint":
        cutoff = p.get("not_before", "")
        coverage = result.get("field_coverage", [])
        result["evidence"] = [e for c in coverage for e in c["evidence"]][:20]
        if not coverage or not isinstance(cutoff, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", cutoff):
            result.update(reason="日期规则缺少明确字段或比较日期")
        else:
            try:
                reference = date.fromisoformat(cutoff)
                if all(c["status"] == "covered" for c in coverage):
                    values = [date.fromisoformat(c["values"][0]) for c in coverage]
                    ok = all(v >= reference for v in values)
                    result.update(
                        verdict="pass" if ok else "fail",
                        reason=f"日期应不早于 {cutoff}（含当日）；读取到 {', '.join(map(str, values))}",
                        next_action="" if ok else "提供满足日期要求的材料",
                    )
                else:
                    result.update(
                        reason=f"并非每份对应材料都能唯一读取有效的「{field}」日期",
                        next_action="逐份补充或确认日期；不根据其他文件的重复日期推断",
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
