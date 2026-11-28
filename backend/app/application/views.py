"""Case projections composed from documents, reports and runs."""

from sqlalchemy import select

from ..models import Message, RuleSet, Run
from .documents import doc_view, documents_for
from .library_links import linked_documents
from .reports import checklist
from .runs import run_view
from .subjects import case_subjects


def case_view(db, c, detail=False):
    result = {
        "id": c.id,
        "workspace_id": c.workspace_id,
        "title": c.title,
        "institution": c.institution,
        "kind": c.kind,
        "scenario": c.scenario_snapshot or None,
        "deadline": c.deadline,
        "revision": c.revision,
        "archived": c.archived,
        "facts": c.facts,
        "created_at": c.created_at.isoformat(),
        "updated_at": c.updated_at.isoformat(),
        "checklist": checklist(db, c),
    }
    if detail:
        result["document_links"] = linked_documents(db, c)
        result["subjects"] = case_subjects(db, c)
        result["documents"] = [doc_view(d, False) for d in documents_for(db, c.id)]
        result["rule_sets"] = [
            {"id": r.id, "version": r.version, "status": r.status, "requirements": r.requirements}
            for r in db.scalars(
                select(RuleSet).where(RuleSet.case_id == c.id).order_by(RuleSet.version.desc())
            )
        ]
        result["messages"] = [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at.isoformat(),
                "run_id": m.run_id,
            }
            for m in db.scalars(
                select(Message)
                .where(Message.case_id == c.id, Message.role.in_(["user", "assistant"]))
                .order_by(Message.created_at)
            )
            if m.content and not (m.role == "assistant" and (m.data or {}).get("tool_calls"))
        ]
        result["runs"] = [
            run_view(r)
            for r in db.scalars(
                select(Run).where(Run.case_id == c.id).order_by(Run.created_at.desc()).limit(30)
            )
        ]
    return result
