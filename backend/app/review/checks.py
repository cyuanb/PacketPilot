"""Deterministic per-requirement checks over an immutable input snapshot."""

import re
from datetime import date

from ..schemas import Finding, Requirement
from .conditions import condition_value
from .evidence import excerpts
from .fields import field_coverage
from .matching import candidates, material_identity


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
    from .advanced import evaluate_rules

    return evaluate_rules(snapshot)
