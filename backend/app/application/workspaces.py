"""One owner-controlled workspace per account; no invitation or membership mutation API."""

from fastapi import HTTPException
from sqlalchemy import select

from ..models import Membership, User, Workspace


def personal_workspace(db, user_id, lock=False):
    workspace = db.scalar(select(Workspace).where(Workspace.owner_id == user_id))
    if not workspace:
        # Serialize first-use provisioning without changing an existing membership.
        user = db.scalar(select(User).where(User.id == user_id).with_for_update())
        if not user:
            raise HTTPException(401, "请先登录")
        workspace = db.scalar(select(Workspace).where(Workspace.owner_id == user_id))
        if not workspace:
            workspace = Workspace(owner_id=user_id)
            db.add(workspace)
            db.flush()
            db.add(Membership(workspace_id=workspace.id, user_id=user_id, role="owner"))
            db.flush()
    membership = db.get(Membership, (workspace.id, user_id))
    if not membership or membership.role != "owner":
        raise HTTPException(403, "没有工作空间访问权限")
    if lock:
        workspace = db.scalar(
            select(Workspace)
            .where(Workspace.id == workspace.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    return workspace


def workspace_view(workspace):
    return {"id": workspace.id, "name": workspace.name, "revision": workspace.revision, "role": "owner"}
