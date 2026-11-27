"""Coverage gates for model-proposed conclusions, independent of model instructions."""

from ..schemas import Requirement
from .evidence import verify_evidence
from .matching import candidates
from .structure import scoped_documents


def validate_semantic(finding, raw_rule, snapshot):
    rule = Requirement.model_validate(raw_rule)
    scoped, error = scoped_documents(rule, snapshot["documents"], snapshot.get("subjects", []))
    matched = candidates(rule, scoped)
    allowed = {d["id"] for d in matched}
    verify_evidence(finding["evidence"], matched, "material")
    if finding["verdict"] == "unknown":
        return
    if error or not matched or any(d["parse_status"] != "ready" for d in matched):
        raise ValueError("材料范围不明确或读取不完整，不能给出确定语义结论")
    if not {e["document_id"] for e in finding["evidence"]}.issubset(allowed):
        raise ValueError("语义引用越出了本项主体或槽位")
    criteria = rule.parameters.get("criteria") or [rule.title]
    coverage = finding.get("semantic_coverage", [])
    if len(coverage) != len(criteria) or {c["criterion"] for c in coverage} != set(criteria):
        raise ValueError("必须逐一覆盖每个语义检查点，不能用单条引用代表全部结论")
    for row in coverage:
        verify_evidence(row["evidence"], matched, "material")
        if row["verdict"] != "unknown" and not row["evidence"]:
            raise ValueError("每个确定检查点都必须有支持该点的原文证据")
        if finding["verdict"] == "pass" and (
            row["verdict"] != "pass" or {e["document_id"] for e in row["evidence"]} != allowed
        ):
            raise ValueError("通过需要每个检查点覆盖所有对应材料，遗漏或未知不能提升为通过")
    if finding["verdict"] == "fail" and not any(c["verdict"] == "fail" for c in coverage):
        raise ValueError("不通过结论必须对应具体未满足的检查点")
