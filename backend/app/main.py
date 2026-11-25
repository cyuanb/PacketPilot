import asyncio
import hashlib
import html
import json
import secrets
import time
from collections import defaultdict
from datetime import timedelta
from pathlib import Path
from urllib.parse import quote

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .config import ROOT, settings
from .db import SessionLocal, get_db, now, uid
from .models import Attestation, Audit, AuthSession, Case, Document, Message, RuleSet, Run, RunEvent, User
from .parsing import MIMES
from .schemas import CaseInput, ChatInput, FactInput, RevisionInput, RulesInput, TextInput
from .services import (
    bump,
    case_for,
    case_view,
    checklist,
    doc_view,
    documents_for,
    enqueue,
    expect_revision,
    run_view,
    save_rules,
)

app = FastAPI(title="PacketPilot API", version="0.1.0", docs_url="/api/docs")
hasher = PasswordHasher()
login_attempts = defaultdict(list)


@app.middleware("http")
async def request_boundary(request: Request, call_next):
    request_id = secrets.token_hex(8)
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        origin = request.headers.get("origin")
        allowed = {settings.app_origin, "http://localhost:5173", "http://127.0.0.1:5173"}
        if (origin and origin not in allowed) or (not origin and request.headers.get("x-packetpilot") != "1"):
            return JSONResponse(
                {"code": "origin_rejected", "message": "请求来源无效", "request_id": request_id},
                status_code=403,
            )
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Cache-Control"] = "no-store" if request.url.path.startswith("/api") else "no-cache"
    return response


@app.exception_handler(HTTPException)
async def http_error(request, exc):
    return JSONResponse(
        {"code": f"http_{exc.status_code}", "message": exc.detail}, status_code=exc.status_code
    )


def current_user(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("packetpilot_session", "")
    session = db.get(AuthSession, hashlib.sha256(token.encode()).hexdigest()) if token else None
    if not session or session.expires_at < now():
        raise HTTPException(401, "请先登录")
    return db.get(User, session.user_id)


class LoginInput(BaseModel):
    username: str = Field(max_length=80)
    password: str = Field(max_length=200)


@app.post("/api/v1/auth/login")
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


@app.post("/api/v1/auth/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    token = request.cookies.get("packetpilot_session", "")
    db.execute(
        delete(AuthSession).where(AuthSession.token_hash == hashlib.sha256(token.encode()).hexdigest())
    )
    db.commit()
    response.delete_cookie("packetpilot_session")
    return {"ok": True}


@app.get("/api/v1/me")
def me(user=Depends(current_user)):
    return {"username": user.username}


@app.get("/api/health")
def health(db: Session = Depends(get_db)):
    from sqlalchemy import text

    db.execute(text("SELECT 1"))
    return {"status": "ok", "version": "0.1.0"}


@app.get("/api/v1/capabilities")
def capabilities(user=Depends(current_user)):
    return {
        "model": settings.llm_model,
        "model_configured": bool(settings.llm_api_key and settings.llm_base_url),
        "ocr": False,
        "formats": list(MIMES),
        "max_file_mb": 20,
        "inference": "所需文本片段会发送至配置的模型服务，原件保存在本机。",
    }


@app.post("/api/v1/model/check")
def model_check(user=Depends(current_user)):
    import httpx

    try:
        with httpx.Client(timeout=20, trust_env=False) as client:
            r = client.post(
                settings.llm_base_url.rstrip("/") + "/chat/completions",
                headers={"Authorization": "Bearer " + settings.llm_api_key},
                json={
                    "model": settings.llm_model,
                    "messages": [{"role": "user", "content": "请回复连接正常。"}],
                    "max_tokens": 30,
                },
            )
            return {"ok": r.is_success, "status": r.status_code, "model": settings.llm_model}
    except Exception:
        return {"ok": False, "message": "模型服务暂时无法连接，请检查内网连接和本地配置"}


@app.get("/api/v1/cases")
def list_cases(user=Depends(current_user), db: Session = Depends(get_db)):
    return [
        case_view(db, c)
        for c in db.scalars(select(Case).where(Case.owner_id == user.id).order_by(Case.updated_at.desc()))
    ]


@app.post("/api/v1/cases", status_code=201)
def create_case(body: CaseInput, user=Depends(current_user), db: Session = Depends(get_db)):
    c = Case(owner_id=user.id, **body.model_dump())
    db.add(c)
    db.commit()
    return case_view(db, c, True)


@app.get("/api/v1/cases/{case_id}")
def get_case(case_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    return case_view(db, case_for(db, user.id, case_id), True)


class CaseUpdate(CaseInput):
    revision: int
    archived: bool = False


@app.patch("/api/v1/cases/{case_id}")
def update_case(case_id: str, body: CaseUpdate, user=Depends(current_user), db: Session = Depends(get_db)):
    c = case_for(db, user.id, case_id, True)
    expect_revision(c, body.revision)
    for k, v in body.model_dump(exclude={"revision"}).items():
        setattr(c, k, v)
    bump(db, c, "case.updated")
    db.commit()
    return case_view(db, c, True)


@app.delete("/api/v1/cases/{case_id}")
def delete_case(case_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    c = case_for(db, user.id, case_id, True)
    keys = list(db.scalars(select(Document.storage_key).where(Document.case_id == c.id)))
    db.delete(c)
    db.commit()
    for key in keys:
        if key:
            (settings.storage / key).unlink(missing_ok=True)
    return {"ok": True}


@app.post("/api/v1/cases/{case_id}/facts/confirm")
def facts(case_id: str, body: FactInput, user=Depends(current_user), db: Session = Depends(get_db)):
    c = case_for(db, user.id, case_id, True)
    expect_revision(c, body.revision)
    if any(len(k) > 100 or len(str(v)) > 1000 for k, v in body.facts.items()):
        raise HTTPException(422, "背景字段过长")
    c.facts = body.facts
    bump(db, c, "facts.confirmed")
    db.commit()
    return case_view(db, c, True)


@app.post("/api/v1/cases/{case_id}/sources/text", status_code=201)
def text_source(case_id: str, body: TextInput, user=Depends(current_user), db: Session = Depends(get_db)):
    c = case_for(db, user.id, case_id, True)
    d = Document(
        case_id=c.id,
        title=body.title,
        purpose=body.purpose,
        category=body.category,
        filename=body.title + ".txt",
        mime="text/plain",
        size=len(body.text.encode()),
        sha256=hashlib.sha256(body.text.encode()).hexdigest(),
        parse_status="ready",
        pages=[{"number": 1, "label": "全文", "text": body.text}],
        parse_method="pasted",
    )
    db.add(d)
    bump(db, c, "document.added")
    db.commit()
    return doc_view(d)


@app.post("/api/v1/cases/{case_id}/documents", status_code=201)
async def upload(
    case_id: str,
    file: UploadFile = File(...),
    purpose: str = Form("material"),
    category: str = Form(""),
    replace_id: str = Form(""),
    user=Depends(current_user),
    db: Session = Depends(get_db),
):
    c = case_for(db, user.id, case_id, True)
    if purpose not in ("source", "material") or len(category) > 100:
        raise HTTPException(422, "无效材料用途或分类")
    active = documents_for(db, c.id)
    if len(active) >= 30 and not replace_id:
        raise HTTPException(422, "每事项最多 30 份材料")
    filename = Path(file.filename or "file").name[:250]
    suffix = Path(filename).suffix.lower()
    if suffix not in MIMES:
        raise HTTPException(415, "支持 PDF、DOCX、TXT、MD、PNG 和 JPEG")
    raw = await file.read(settings.max_file_bytes + 1)
    if len(raw) > settings.max_file_bytes:
        raise HTTPException(413, "单文件不能超过 20 MiB")
    if not raw:
        raise HTTPException(422, "文件为空")
    previous = next((d for d in active if d.id == replace_id), None)
    if replace_id and not previous:
        raise HTTPException(409, "待替换材料已变化，请刷新")
    key = uid() + suffix
    settings.storage.mkdir(parents=True, exist_ok=True)
    path = settings.storage / key
    path.write_bytes(raw)
    try:
        d = Document(
            case_id=c.id,
            title=filename,
            purpose=previous.purpose if previous else purpose,
            category=category or (previous.category if previous else ""),
            filename=filename,
            storage_key=key,
            sha256=hashlib.sha256(raw).hexdigest(),
            mime=MIMES[suffix],
            size=len(raw),
        )
        if previous:
            previous.active = False
            d.logical_id, d.version = previous.logical_id, previous.version + 1
        db.add(d)
        bump(db, c, "document.replaced" if previous else "document.added")
        db.flush()
        task, _ = enqueue(db, c, "parse", {"document_id": d.id})
        db.commit()
        return {"document": doc_view(d), "run_id": task.id}
    except Exception:
        path.unlink(missing_ok=True)
        raise


def document_for(db, user, doc_id):
    d = db.get(Document, doc_id)
    if not d:
        raise HTTPException(404, "材料不存在")
    case_for(db, user.id, d.case_id)
    return d


@app.get("/api/v1/documents/{doc_id}")
def document_detail(doc_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    return doc_view(document_for(db, user, doc_id))


@app.get("/api/v1/documents/{doc_id}/content")
def document_content(doc_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    d = document_for(db, user, doc_id)
    if not d.storage_key:
        return Response("\n\n".join(p["text"] for p in d.pages), media_type="text/plain")
    path = settings.storage / d.storage_key
    if not path.is_file():
        raise HTTPException(404, "原件不存在")
    return FileResponse(
        path,
        media_type=d.mime,
        filename=d.filename,
        content_disposition_type="inline"
        if d.mime in ("application/pdf", "image/png", "image/jpeg")
        else "attachment",
    )


class CorrectionInput(BaseModel):
    text: str = Field(min_length=1, max_length=200000)
    revision: int


@app.post("/api/v1/documents/{doc_id}/correction")
def correction(doc_id: str, body: CorrectionInput, user=Depends(current_user), db: Session = Depends(get_db)):
    old = document_for(db, user, doc_id)
    c = case_for(db, user.id, old.case_id, True)
    expect_revision(c, body.revision)
    if not old.active:
        raise HTTPException(409, "材料已被替换")
    old.active = False
    d = Document(
        case_id=c.id,
        logical_id=old.logical_id,
        version=old.version + 1,
        title=old.title,
        purpose=old.purpose,
        category=old.category,
        filename=old.filename,
        mime=old.mime,
        storage_key=old.storage_key,
        sha256=old.sha256,
        size=old.size,
        parse_method="user_corrected",
        parse_status="ready",
        parse_note="用户提供校订文本；应结合原件复核。",
        pages=[{"number": 1, "label": "人工校订文本", "text": body.text}],
    )
    db.add(d)
    bump(db, c, "document.corrected")
    db.commit()
    return doc_view(d)


@app.delete("/api/v1/documents/{doc_id}")
def delete_document(doc_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    d = document_for(db, user, doc_id)
    c = case_for(db, user.id, d.case_id, True)
    versions = list(db.scalars(select(Document).where(Document.logical_id == d.logical_id)))
    ids = {v.id for v in versions}
    keys = {v.storage_key for v in versions if v.storage_key}
    # Removing original evidence also removes affected historical check snapshots and message traces.
    runs = list(db.scalars(select(Run).where(Run.case_id == c.id)))
    for r in runs:
        if any(x["id"] in ids for x in r.snapshot.get("documents", [])):
            if c.current_check_id == r.id:
                c.current_check_id = None
            db.delete(r)
    for rules in db.scalars(select(RuleSet).where(RuleSet.case_id == c.id)):
        if ids.intersection(rules.source_ids):
            rules.status = "source_removed"
            if c.active_rules_id == rules.id:
                c.active_rules_id = None
    for v in versions:
        db.delete(v)
    bump(db, c, "document.deleted")
    db.commit()
    for key in keys:
        (settings.storage / key).unlink(missing_ok=True)
    return {"ok": True}


@app.post("/api/v1/cases/{case_id}/rule-sets")
def edit_rules(case_id: str, body: RulesInput, user=Depends(current_user), db: Session = Depends(get_db)):
    c = case_for(db, user.id, case_id, True)
    expect_revision(c, body.revision)
    try:
        r = save_rules(
            db, c, [v.model_dump() for v in body.requirements], [doc_view(d) for d in documents_for(db, c.id)]
        )
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    db.commit()
    return {"id": r.id, "version": r.version}


@app.post("/api/v1/rule-sets/{rules_id}/activate")
def activate(rules_id: str, body: RevisionInput, user=Depends(current_user), db: Session = Depends(get_db)):
    r = db.get(RuleSet, rules_id)
    if not r:
        raise HTTPException(404, "要求版本不存在")
    c = case_for(db, user.id, r.case_id, True)
    expect_revision(c, body.revision)
    active_ids = {
        d.id for d in documents_for(db, c.id) if d.purpose == "source" and d.parse_status == "ready"
    }
    if r.status != "draft" or not set(r.source_ids).issubset(active_ids):
        raise HTTPException(409, "此草稿不可启用或来源版本已更新")
    if c.active_rules_id:
        db.get(RuleSet, c.active_rules_id).status = "superseded"
    r.status, c.active_rules_id = "active", r.id
    bump(db, c, "rules.activated", {"rules_id": r.id})
    db.commit()
    return case_view(db, c, True)


def start_run(db, user, case_id, kind, revision, payload, key):
    c = case_for(db, user.id, case_id, True)
    # Idempotent replays must work even if an earlier request changed the revision later.
    if key:
        prior = db.scalar(select(Run).where(Run.case_id == c.id, Run.idempotency_key == key))
        if prior:
            r, _ = enqueue(db, c, kind, payload, key)
            return run_view(r)
    expect_revision(c, revision)
    if kind == "check" and not c.active_rules_id:
        raise HTTPException(422, "请先启用一版申请要求")
    if kind == "check":
        from .services import snapshot

        if not snapshot(db, c)["requirements"]:
            raise HTTPException(409, "通知来源已变化，请重新提取并启用要求")
    if kind == "extract" and not any(
        d.purpose == "source" and d.parse_status == "ready" for d in documents_for(db, c.id)
    ):
        raise HTTPException(422, "请先导入可读取的申请通知")
    running = db.scalar(
        select(Run).where(Run.case_id == c.id, Run.kind != "parse", Run.status.in_(["queued", "running"]))
    )
    if running:
        raise HTTPException(409, "当前事项已有分析任务，请等待完成或取消")
    r, created = enqueue(db, c, kind, payload, key)
    if created and payload.get("text"):
        db.add(Message(case_id=c.id, run_id=r.id, role="user", content=payload["text"]))
    db.commit()
    return run_view(r)


@app.post("/api/v1/cases/{case_id}/extract", status_code=202)
def extract(
    case_id: str,
    body: RevisionInput,
    user=Depends(current_user),
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(None),
):
    return start_run(db, user, case_id, "extract", body.revision, {}, idempotency_key)


@app.post("/api/v1/cases/{case_id}/checks", status_code=202)
def check(
    case_id: str,
    body: RevisionInput,
    user=Depends(current_user),
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(None),
):
    return start_run(db, user, case_id, "check", body.revision, {}, idempotency_key)


@app.post("/api/v1/cases/{case_id}/messages", status_code=202)
def chat(
    case_id: str,
    body: ChatInput,
    user=Depends(current_user),
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(None),
):
    return start_run(db, user, case_id, "chat", body.revision, {"text": body.text}, idempotency_key)


def run_for(db, user, run_id):
    r = db.get(Run, run_id)
    if not r:
        raise HTTPException(404, "运行不存在")
    case_for(db, user.id, r.case_id)
    return r


@app.get("/api/v1/runs/{run_id}")
def get_run(run_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    return run_view(run_for(db, user, run_id))


@app.post("/api/v1/runs/{run_id}/cancel")
def cancel(run_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    r = run_for(db, user, run_id)
    r.cancel_requested = True
    if r.status == "queued":
        r.status = "cancelled"
    db.commit()
    return {"status": r.status, "cancel_requested": True}


@app.get("/api/v1/runs/{run_id}/events")
async def events(
    run_id: str, request: Request, after: int = 0, user=Depends(current_user), db: Session = Depends(get_db)
):
    run_for(db, user, run_id)
    try:
        cursor = max(after, int(request.headers.get("last-event-id", "0")))
    except ValueError:
        raise HTTPException(422, "无效事件游标")

    async def stream():
        nonlocal cursor
        while not await request.is_disconnected():
            with SessionLocal() as session:
                r = session.get(Run, run_id)
                if not r:
                    break
                batch = list(
                    session.scalars(
                        select(RunEvent)
                        .where(RunEvent.run_id == run_id, RunEvent.id > cursor)
                        .order_by(RunEvent.id)
                        .limit(100)
                    )
                )
                terminal = r.status not in ("queued", "running")
                for e in batch:
                    cursor = e.id
                    yield f"id: {e.id}\nevent: {e.event}\ndata: {json.dumps(e.data, ensure_ascii=False)}\n\n"
            if terminal and len(batch) < 100:
                yield "event: done\ndata: {}\n\n"
                break
            yield ": heartbeat\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"X-Accel-Buffering": "no"})


class AttestationInput(RevisionInput):
    requirement_id: str
    note: str = Field(min_length=1, max_length=1000)


@app.post("/api/v1/cases/{case_id}/attestations")
def attest(case_id: str, body: AttestationInput, user=Depends(current_user), db: Session = Depends(get_db)):
    c = case_for(db, user.id, case_id, True)
    expect_revision(c, body.revision)
    report = checklist(db, c)
    f = next((f for f in report["findings"] if f["requirement_id"] == body.requirement_id), None)
    if not f or f["method"] != "manual" or not report["can_export"] or f["applicability"] != "applicable":
        raise HTTPException(422, "仅可对当前版本的人工检查项确认")
    db.add(Attestation(case_id=c.id, revision=c.revision, requirement_id=body.requirement_id, note=body.note))
    db.add(Audit(case_id=c.id, action="manual.confirmed", data={"requirement_id": body.requirement_id}))
    db.commit()
    return checklist(db, c)


@app.get("/api/v1/cases/{case_id}/export")
def export(case_id: str, format: str = "html", user=Depends(current_user), db: Session = Depends(get_db)):
    c = case_for(db, user.id, case_id)
    report = checklist(db, c)
    if not report["can_export"]:
        raise HTTPException(409, "请先完成当前版本的检查再导出")
    rules = {r["id"]: r for r in report["requirements"]}
    lines = [
        f"# {c.title} · 材料预检",
        "",
        f"检查修订：{report['checked_revision']}",
        f"检查时间：{report['checked_at']}",
        f"检查引擎：{report['engine_version']}",
        f"要求覆盖：{report['coverage']['evaluated_count']}/{report['coverage']['expected_count']}",
        "",
        "本结果用于材料准备，不代表官方审核结论。",
        "",
    ]
    for f in report["findings"]:
        lines += [
            f"## {rules.get(f['requirement_id'], {}).get('title', f['requirement_id'])}",
            f"状态：{f['verdict']}；适用性：{f['applicability']}；方式：{f['method']}",
            f["reason"],
            f"下一步：{f['next_action'] or '无'}",
            "",
        ]
        for e in f["evidence"]:
            lines += [f"> 材料版本 {e['document_id']} · 位置 {e['page']}：{e['quote']}", ""]
        for covered in f.get("field_coverage", []):
            lines += [f"逐材料字段覆盖：{covered['document_id']} · {covered['field']} · {covered['status']}"]
        for candidate in f.get("material_matches", []):
            lines += [f"候选材料：{candidate['document_id']} · {candidate['reason']}"]
    for a in report["attestations"]:
        lines += [f"人工确认 {a['requirement_id']}：{a['note']}（{a['created_at']}）"]
    content = "\n".join(lines)
    if format == "html":
        content = (
            '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>PacketPilot 预检结果</title><style>body{max-width:900px;margin:48px auto;padding:20px;font:16px/1.8 system-ui;color:#173a35}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:inherit}</style><body><pre>'
            + html.escape(content)
            + "</pre></body></html>"
        )
    elif format != "md":
        raise HTTPException(422, "支持 html 或 md")
    return Response(
        content,
        media_type="text/html" if format == "html" else "text/markdown",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(c.title + '-预检.' + format)}"},
    )


@app.get("/api/v1/cases/{case_id}/audit")
def audit(case_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    c = case_for(db, user.id, case_id)
    return [
        {"action": a.action, "data": a.data, "at": a.created_at.isoformat()}
        for a in db.scalars(select(Audit).where(Audit.case_id == c.id).order_by(Audit.id.desc()).limit(100))
    ]


@app.post("/api/v1/demo", status_code=201)
def demo(user=Depends(current_user), db: Session = Depends(get_db)):
    from .demo import create_demo

    c = create_demo(db, user.id)
    db.commit()
    return case_view(db, c, True)


dist = ROOT / "frontend" / "dist"
if dist.exists():
    app.mount("/", StaticFiles(directory=dist, html=True), name="web")
