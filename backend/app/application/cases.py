"""Case ownership, optimistic revisions and audit updates."""

from fastapi import HTTPException
from sqlalchemy import select

from ..db import now
from ..models import Audit, Case


def case_for(db, user_id, case_id, lock=False):
    query = select(Case).where(Case.id == case_id, Case.owner_id == user_id)
    if lock:
        query = query.with_for_update()
    item = db.scalar(query)
    if not item:
        raise HTTPException(404, "事项不存在")
    return item


def expect_revision(case, revision):
    if case.revision != revision:
        raise HTTPException(409, "材料或要求已变化，请刷新后重试")


def bump(db, case, action, data=None):
    case.revision += 1
    case.updated_at = now()
    db.add(Audit(case_id=case.id, action=action, data=data or {}))
