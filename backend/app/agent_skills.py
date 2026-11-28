"""Explicit, inspectable routing to local task procedures."""

import hashlib

from .config import ROOT

SKILLS = {
    "application-guidance": "材料准备指导",
    "requirement-extraction": "通知要求提取",
    "application-preflight": "申请材料预检",
    "amendment-recheck": "补件变化复检",
    "evidence-explanation": "检查依据解释",
}


def select_skill(kind, text="", previous=False):
    if kind == "extract":
        return "requirement-extraction"
    if kind == "check":
        return "amendment-recheck" if previous else "application-preflight"
    if any(term in text for term in ("提取要求", "提取通知", "整理通知", "生成要求", "提取申请", "提取这份")):
        return "requirement-extraction"
    if any(term in text for term in ("复检", "补件后", "变化", "重新检查")):
        return "amendment-recheck" if previous else "application-preflight"
    if any(term in text for term in ("解释", "依据", "为什么", "原文", "证据")):
        return "evidence-explanation"
    if any(term in text for term in ("预检", "检查材料", "缺哪些", "缺什么", "还缺", "核对材料")):
        return "application-preflight"
    return "application-guidance"


def load_skill(name):
    if name not in SKILLS:
        raise ValueError("未知任务流程")
    content = (ROOT / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
    metadata = {
        "name": name,
        "label": SKILLS[name],
        "hash": hashlib.sha256(content.encode()).hexdigest(),
        "steps": [
            line[3:].strip()
            for line in content.splitlines()
            if len(line) > 3 and line[0].isdigit() and line[1:3] == ". "
        ],
    }
    return content, metadata
