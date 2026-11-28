"""Owner review is distinct from parsing, matching and requirement verdicts."""

import hashlib
import json

ASSIGNMENT_FIELDS = ("state", "subject_id", "document_type", "slot_ids", "variant", "pair_key", "issuer")


def review_basis(doc):
    assignment = {k: v for k, v in (doc.assignment or {}).items() if k in ASSIGNMENT_FIELDS}
    return hashlib.sha256(
        json.dumps(
            {
                "document_id": doc.id,
                "parse_revision_id": doc.current_parse_id,
                "category": doc.category,
                "assignment": assignment,
            },
            sort_keys=True,
            ensure_ascii=False,
        ).encode()
    ).hexdigest()


def material_review(doc):
    record = (doc.assignment or {}).get("_confirmation") or {}
    state = "pending"
    if record.get("confirmed"):
        state = (
            "confirmed"
            if record.get("basis") == review_basis(doc) and doc.active and doc.parse_status != "queued"
            else "stale"
        )
    if (doc.assignment or {}).get("state") == "rejected":
        state = "excluded"
    return {
        "state": state,
        "confirmed_at": record.get("at"),
        "parse_revision_id": record.get("parse_revision_id"),
    }
