"""Independent field and date coverage for each candidate document."""

import re
from datetime import date

from .common import norm


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
