import hashlib
import secrets
import time
from collections import defaultdict

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..db import get_db, now
from ..models import AuthSession, RecoveryCode, User
from ..schemas import StrictModel
from .dependencies import current_user

router = APIRouter()
attempts = defaultdict(list)


class PasswordInput(StrictModel):
    password: str = Field(min_length=1, max_length=200)


class RecoverInput(StrictModel):
    username: str = Field(max_length=80)
    recovery_code: str = Field(min_length=20, max_length=100)
    new_password: str = Field(min_length=12, max_length=200)


def check_password(user, password):
    try:
        PasswordHasher().verify(user.password_hash, password)
    except VerifyMismatchError as error:
        raise HTTPException(401, "密码不正确") from error


@router.get("/api/v1/account/sessions")
def sessions(request: Request, user=Depends(current_user), db: Session = Depends(get_db)):
    current = hashlib.sha256(request.cookies.get("packetpilot_session", "").encode()).hexdigest()
    return [
        {"id": s.token_hash, "current": s.token_hash == current, "expires_at": s.expires_at.isoformat()}
        for s in db.scalars(
            select(AuthSession).where(AuthSession.user_id == user.id, AuthSession.expires_at > now())
        )
    ]


@router.delete("/api/v1/account/sessions/{session_id}")
def revoke_session(session_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    db.execute(
        delete(AuthSession).where(AuthSession.user_id == user.id, AuthSession.token_hash == session_id)
    )
    db.commit()
    return {"ok": True}


@router.post("/api/v1/account/recovery-code")
def recovery_code(body: PasswordInput, user=Depends(current_user), db: Session = Depends(get_db)):
    check_password(user, body.password)
    code = secrets.token_urlsafe(32)
    row = db.get(RecoveryCode, user.id)
    if row:
        row.token_hash = hashlib.sha256(code.encode()).hexdigest()
        row.created_at = now()
    else:
        db.add(RecoveryCode(user_id=user.id, token_hash=hashlib.sha256(code.encode()).hexdigest()))
    db.commit()
    return {"recovery_code": code, "notice": "只显示一次，请离线保管；重新生成后旧码失效"}


@router.post("/api/v1/account/recover")
def recover(body: RecoverInput, request: Request, db: Session = Depends(get_db)):
    host = request.client.host if request.client else "local"
    stamp = time.monotonic()
    attempts[host] = [t for t in attempts[host] if stamp - t < 300]
    if len(attempts[host]) >= 5:
        raise HTTPException(429, "尝试次数过多，请稍后重试")
    attempts[host].append(stamp)
    u = db.scalar(select(User).where(User.username == body.username).with_for_update())
    row = db.get(RecoveryCode, u.id) if u else None
    if not row or not secrets.compare_digest(
        row.token_hash, hashlib.sha256(body.recovery_code.encode()).hexdigest()
    ):
        raise HTTPException(401, "账号或恢复码不正确")
    u.password_hash = PasswordHasher().hash(body.new_password)
    db.delete(row)
    db.execute(delete(AuthSession).where(AuthSession.user_id == u.id))
    db.commit()
    return {"ok": True, "notice": "密码已重置，所有旧会话失效；登录后请重新生成恢复码"}
