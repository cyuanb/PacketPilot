"""Document-version evidence anchoring and excerpt selection."""

from .common import norm


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
