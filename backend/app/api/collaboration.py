"""Explicitly scoped collaboration; never grants access to owner-only case endpoints."""

import hashlib
import secrets
from datetime import timedelta
from pathlib import Path
from typing import Literal

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile
from pydantic import Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..application.assets import capture_document, discard_uncommitted_file
from ..application.cases import bump, case_for
from ..application.documents import doc_view, documents_for
from ..application.packets import original_bytes
from ..application.runs import enqueue
from ..config import settings
from ..db import get_db, now, uid
from ..models import AccessGrant, Case, CollectionSubmission, Document, ReviewComment, User
from ..parsing import MIMES
from ..review.evidence import verify_evidence
from ..schemas import StrictModel
from .dependencies import current_user

router = APIRouter()


class InviteInput(StrictModel):
    role: Literal["reader", "reviewer", "collector"]
    document_ids: list[str] = Field(default_factory=list, max_length=30)
    days: int = Field(default=7, ge=1, le=30)


class AcceptInput(StrictModel):
    token: str = Field(min_length=20, max_length=100)
    username: str = Field(min_length=3, max_length=80, pattern=r"^[a-zA-Z0-9_.-]+$")
    password: str = Field(min_length=1, max_length=200)


class CommentInput(StrictModel):
    document_id: str
    parse_revision_id: str | None = None
    page: int = Field(ge=1)
    quote: str = Field(default="", max_length=1000)
    content: str = Field(min_length=1, max_length=2000)
    decision: Literal["comment", "approved", "returned"] = "comment"


class ReviewSubmission(StrictModel):
    decision: Literal["accept", "return"]
    note: str = Field(default="", max_length=2000)
    category: str = Field(default="", max_length=100)


def grant_for(db, user, identifier):
    grant = db.scalar(select(AccessGrant).where(AccessGrant.id == identifier).with_for_update())
    if not grant or grant.revoked or grant.expires_at <= now() or grant.user_id != user.id:
        raise HTTPException(404, "授权不存在、已过期或已撤销")
    return grant


def grant_view(db, g):
    u = db.get(User, g.user_id) if g.user_id else None
    return {
        "id": g.id,
        "case_id": g.case_id,
        "role": g.role,
        "document_ids": g.document_ids,
        "username": u.username if u else None,
        "expires_at": g.expires_at.isoformat(),
        "revoked": g.revoked,
    }


@router.post("/api/v1/cases/{case_id}/invitations", status_code=201)
def invite(case_id: str, body: InviteInput, user=Depends(current_user), db: Session = Depends(get_db)):
    c = case_for(db, user.id, case_id, True)
    docs = {d.id for d in documents_for(db, c.id) if d.purpose == "material"}
    if not set(body.document_ids).issubset(docs) or body.role != "collector" and not body.document_ids:
        raise HTTPException(422, "请明确选择授权材料版本")
    if body.role == "collector" and body.document_ids:
        raise HTTPException(422, "收集授权不共享已有材料")
    token = secrets.token_urlsafe(32)
    g = AccessGrant(
        case_id=c.id,
        role=body.role,
        document_ids=body.document_ids,
        token_hash=hashlib.sha256(token.encode()).hexdigest(),
        expires_at=now() + timedelta(days=body.days),
    )
    db.add(g)
    db.commit()
    return {**grant_view(db, g), "token": token, "notice": "请自行安全转交邀请码；只显示一次，不自动发送消息"}


@router.post("/api/v1/invitations/accept")
def accept(body: AcceptInput, request: Request, db: Session = Depends(get_db)):
    import time

    from .account import attempts

    host = "invite:" + (request.client.host if request.client else "local")
    stamp = time.monotonic()
    attempts[host] = [t for t in attempts[host] if stamp - t < 300]
    if len(attempts[host]) >= 10:
        raise HTTPException(429, "尝试次数过多，请稍后重试")
    attempts[host].append(stamp)
    g = db.scalar(
        select(AccessGrant)
        .where(AccessGrant.token_hash == hashlib.sha256(body.token.encode()).hexdigest())
        .with_for_update()
    )
    if not g or g.revoked or g.expires_at <= now() or g.user_id:
        raise HTTPException(404, "邀请码无效或已使用")
    u = db.scalar(select(User).where(User.username == body.username))
    if u:
        try:
            PasswordHasher().verify(u.password_hash, body.password)
        except VerifyMismatchError as error:
            raise HTTPException(401, "账号凭据不正确") from error
    else:
        if len(body.password) < 12:
            raise HTTPException(422, "新账号密码至少 12 位")
        u = User(username=body.username, password_hash=PasswordHasher().hash(body.password))
        db.add(u)
        db.flush()
    g.user_id = u.id
    db.commit()
    return {"ok": True, "notice": "邀请已接受，请登录后打开协作入口"}


@router.get("/api/v1/cases/{case_id}/collaboration")
def owner_collaboration(case_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    case_for(db, user.id, case_id)
    grants = list(db.scalars(select(AccessGrant).where(AccessGrant.case_id == case_id)))
    ids = [g.id for g in grants]
    comments = []
    for x in db.scalars(
        select(ReviewComment).where(ReviewComment.grant_id.in_(ids)).order_by(ReviewComment.created_at)
    ):
        d = db.get(Document, x.document_id)
        comments.append(
            {
                "id": x.id,
                "document_id": x.document_id,
                "page": x.page,
                "quote": x.quote,
                "content": x.content,
                "decision": x.decision,
                "stale": not d or not d.active or d.current_parse_id != x.parse_revision_id,
                "at": x.created_at.isoformat(),
            }
        )
    submissions = [
        {
            "id": s.id,
            "filename": s.filename,
            "sha256": s.sha256,
            "status": s.status,
            "note": s.note,
            "document_id": s.document_id,
        }
        for s in db.scalars(select(CollectionSubmission).where(CollectionSubmission.grant_id.in_(ids)))
    ]
    return {"grants": [grant_view(db, g) for g in grants], "comments": comments, "submissions": submissions}


@router.delete("/api/v1/invitations/{grant_id}")
def revoke(grant_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    g = db.get(AccessGrant, grant_id)
    if not g:
        raise HTTPException(404, "授权不存在")
    case_for(db, user.id, g.case_id, True)
    db.refresh(g, with_for_update=True)
    g.revoked = True
    db.commit()
    return {"ok": True}


@router.get("/api/v1/shared")
def shared(user=Depends(current_user), db: Session = Depends(get_db)):
    return [
        {**grant_view(db, g), "title": db.get(Case, g.case_id).title}
        for g in db.scalars(
            select(AccessGrant).where(
                AccessGrant.user_id == user.id, ~AccessGrant.revoked, AccessGrant.expires_at > now()
            )
        )
    ]


@router.get("/api/v1/shared/{grant_id}")
def shared_detail(grant_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    g = grant_for(db, user, grant_id)
    docs = (
        list(
            db.scalars(
                select(Document).where(
                    Document.id.in_(g.document_ids), Document.case_id == g.case_id, Document.active
                )
            )
        )
        if g.role != "collector"
        else []
    )
    return {
        **grant_view(db, g),
        "title": db.get(Case, g.case_id).title,
        "documents": [doc_view(d) for d in docs],
        "submissions": [
            {"id": s.id, "filename": s.filename, "status": s.status, "note": s.note}
            for s in db.scalars(select(CollectionSubmission).where(CollectionSubmission.grant_id == g.id))
        ],
    }


@router.get("/api/v1/shared/{grant_id}/documents/{document_id}/content")
def shared_content(
    grant_id: str, document_id: str, user=Depends(current_user), db: Session = Depends(get_db)
):
    g = grant_for(db, user, grant_id)
    d = db.get(Document, document_id)
    if (
        g.role == "collector"
        or document_id not in g.document_ids
        or not d
        or not d.active
        or d.case_id != g.case_id
    ):
        raise HTTPException(404, "该材料版本未授权")
    return Response(
        original_bytes(db, d),
        media_type=d.mime,
        headers={
            "Content-Disposition": 'attachment; filename="shared-material' + Path(d.filename).suffix + '"'
        },
    )


@router.post("/api/v1/shared/{grant_id}/comments", status_code=201)
def comment(grant_id: str, body: CommentInput, user=Depends(current_user), db: Session = Depends(get_db)):
    g = grant_for(db, user, grant_id)
    d = db.get(Document, body.document_id)
    if (
        g.role != "reviewer"
        or body.document_id not in g.document_ids
        or not d
        or not d.active
        or d.case_id != g.case_id
    ):
        raise HTTPException(403, "没有此材料的复核权限")
    if d.current_parse_id != body.parse_revision_id:
        raise HTTPException(409, "解析版本已变，请重新读取")
    if not any(p["number"] == body.page for p in d.pages):
        raise HTTPException(422, "页面不存在")
    if body.quote:
        try:
            verify_evidence([{"document_id": d.id, "page": body.page, "quote": body.quote}], [doc_view(d)])
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
    db.add(ReviewComment(grant_id=g.id, **body.model_dump()))
    db.commit()
    return {"ok": True, "notice": "他人复核不替代机器检查或本人最终提交确认"}


@router.post("/api/v1/shared/{grant_id}/submissions", status_code=201)
async def submit(
    grant_id: str, file: UploadFile = File(...), user=Depends(current_user), db: Session = Depends(get_db)
):
    g = grant_for(db, user, grant_id)
    if g.role != "collector":
        raise HTTPException(403, "此授权不允许上传")
    if (
        db.scalar(
            select(func.count())
            .select_from(CollectionSubmission)
            .where(CollectionSubmission.grant_id == g.id)
        )
        >= 10
    ):
        raise HTTPException(422, "此收集任务最多 10 份提交")
    filename = Path(file.filename or "file").name[:250]
    if Path(filename).suffix.lower() not in MIMES:
        raise HTTPException(415, "文件类型不支持")
    raw = await file.read(settings.max_file_bytes + 1)
    if not raw or len(raw) > settings.max_file_bytes:
        raise HTTPException(413, "文件为空或过大")
    s = CollectionSubmission(
        grant_id=g.id, filename=filename, content=raw, sha256=hashlib.sha256(raw).hexdigest()
    )
    db.add(s)
    db.commit()
    return {"id": s.id, "status": s.status}


@router.post("/api/v1/submissions/{submission_id}/review")
def accept_submission(
    submission_id: str, body: ReviewSubmission, user=Depends(current_user), db: Session = Depends(get_db)
):
    s = db.get(CollectionSubmission, submission_id)
    if not s:
        raise HTTPException(404, "提交不存在")
    g = db.get(AccessGrant, s.grant_id)
    c = case_for(db, user.id, g.case_id, True)
    db.refresh(s, with_for_update=True)
    if s.status != "submitted":
        raise HTTPException(409, "该提交已经处理")
    if body.decision == "return":
        if not body.note.strip():
            raise HTTPException(422, "请填写退回原因")
        s.status, s.note = "returned", body.note
        db.commit()
        return {"status": s.status}
    if len(documents_for(db, c.id)) >= 30:
        raise HTTPException(422, "事项材料已满")
    key = uid() + Path(s.filename).suffix.lower()
    path = settings.storage / key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(s.content)
    try:
        d = Document(
            case_id=c.id,
            title=s.filename,
            filename=s.filename,
            category=body.category,
            storage_key=key,
            mime=MIMES[path.suffix],
            size=len(s.content),
            sha256=s.sha256,
        )
        db.add(d)
        capture_document(db, c, d)
        bump(db, c, "collection.accepted", {"document_id": d.id})
        enqueue(db, c, "parse", {"document_id": d.id})
        s.document_id = d.id
        s.status = "accepted"
        s.note = body.note
        db.commit()
        return {"status": s.status, "document_id": d.id}
    except Exception:
        discard_uncommitted_file(db, path)
        raise
