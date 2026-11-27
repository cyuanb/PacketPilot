"""Candidate selection and deliberately limited material structure profiles."""

import re

from .common import norm
from .fields import field_coverage


def candidates(requirement, documents):
    token = norm(requirement.document_type)
    material = [
        d
        for d in documents
        if d["purpose"] == "material" and d.get("assignment", {}).get("state") != "rejected"
    ]
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
        if token in norm(d.get("category", ""))
        or any(token in norm(p["text"]) for p in d["pages"])
        or (
            d.get("assignment", {}).get("state") == "accepted"
            and token == norm(d["assignment"].get("document_type", ""))
        )
    ]


# Limited structure checks; these do not verify authenticity.
MATERIAL_PROFILES = {
    "成绩单": (("姓名", "学生姓名"), ("平均绩点", "绩点", "成绩", "课程成绩")),
    "申请表": (("姓名", "申请人"), ("申请类别", "目标院校", "申请项目")),
    "学习计划": (("学习目标",), ("拟修课程", "学习安排")),
    "推荐信": (("姓名", "申请人"), ("推荐意见",)),
    "入职登记表": (("姓名",), ("入职日期", "部门", "岗位")),
    "营业执照": (("名称", "企业名称"), ("统一社会信用代码", "注册号")),
}


def material_identity(document, document_type):
    from .structure import accepted_identity

    accepted = accepted_identity(document, document_type)
    if accepted:
        return accepted
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
