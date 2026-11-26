"""HTTP endpoints for identity."""

import hashlib
import secrets
import time
from collections import defaultdict
from datetime import timedelta

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db, now
from ..models import AuthSession, User
from .dependencies import current_user
from .requests import LoginInput

router = APIRouter()


hasher = PasswordHasher()


login_attempts = defaultdict(list)


@router.post("/api/v1/auth/login")
def login(body: LoginInput, request: Request, response: Response, db: Session = Depends(get_db)):
    identity = request.client.host if request.client else "local"
    stamp = time.monotonic()
    login_attempts[identity] = [t for t in login_attempts[identity] if stamp - t < 300]
    if len(login_attempts[identity]) >= 10:
        raise HTTPException(429, "尝试次数过多，请稍后再试")
    login_attempts[identity].append(stamp)
    user = db.scalar(select(User).where(User.username == body.username))
    valid = False
    if user:
        try:
            valid = hasher.verify(user.password_hash, body.password)
        except VerifyMismatchError:
            pass
    if not valid:
        raise HTTPException(401, "账号或密码不正确")
    login_attempts[identity] = []
    token = secrets.token_urlsafe(32)
    db.add(
        AuthSession(
            token_hash=hashlib.sha256(token.encode()).hexdigest(),
            user_id=user.id,
            expires_at=now() + timedelta(days=7),
        )
    )
    db.commit()
    response.set_cookie(
        "packetpilot_session",
        token,
        httponly=True,
        samesite="strict",
        secure=settings.cookie_secure,
        max_age=604800,
        path="/",
    )
    return {"username": user.username}


@router.post("/api/v1/auth/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    token = request.cookies.get("packetpilot_session", "")
    db.execute(
        delete(AuthSession).where(AuthSession.token_hash == hashlib.sha256(token.encode()).hexdigest())
    )
    db.commit()
    response.delete_cookie("packetpilot_session")
    return {"ok": True}


@router.get("/api/v1/me")
def me(user=Depends(current_user)):
    return {"username": user.username}
