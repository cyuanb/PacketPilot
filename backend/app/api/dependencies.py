"""Cookie-session authentication dependency shared by all protected routes."""

import hashlib

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..db import get_db, now
from ..models import AuthSession, User


def current_user(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("packetpilot_session", "")
    session = db.get(AuthSession, hashlib.sha256(token.encode()).hexdigest()) if token else None
    if not session or session.expires_at < now():
        raise HTTPException(401, "请先登录")
    return db.get(User, session.user_id)
