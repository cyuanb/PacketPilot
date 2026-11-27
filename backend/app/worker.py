import json
import os
import subprocess
import sys
import threading
import time
from datetime import timedelta

from sqlalchemy import or_, select

from .agent import Cancelled, locked_run, run_agent
from .application.cases import bump
from .application.issues import synchronize_issues
from .application.parses import append_parse, ensure_parse
from .application.reports import checklist
from .application.runs import event
from .config import ROOT, settings
from .db import SessionLocal, now
from .models import Case, Document, Message, Run
from .review.aggregation import review_result
from .review.checks import run_checks


def claim():
    with SessionLocal.begin() as db:
        r = db.scalar(
            select(Run)
            .where(or_(Run.status == "queued", (Run.status == "running") & (Run.lease_until < now())))
            .order_by(Run.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if not r:
            return None
        if r.cancel_requested or r.attempt >= 3:
            r.status = "cancelled" if r.cancel_requested else "failed"
            r.error = "任务已取消" if r.cancel_requested else "任务恢复次数达到上限"
            event(db, r.id, "run." + r.status, {"message": r.error})
            return None
        r.fence += 1
        r.attempt += 1
        r.status = "running"
        r.lease_until = now() + timedelta(seconds=60)
        r.updated_at = now()
        event(db, r.id, "run.started", {"attempt": r.attempt})
        return r.id, r.fence, r.kind


def heartbeat(run_id, fence, stop):
    while not stop.wait(15):
        try:
            with SessionLocal.begin() as db:
                r = locked_run(db, run_id, fence)
                r.lease_until = now() + timedelta(seconds=60)
        except Exception:
            return


def parse_task(run_id, fence):
    with SessionLocal() as db:
        r = db.get(Run, run_id)
        doc = db.get(Document, r.payload["document_id"])
        if not doc:
            raise Cancelled()
        key = doc.storage_key
    output = settings.storage / f"parse-{run_id}-{fence}.json"
    environment = {
        k: v for k, v in os.environ.items() if k.upper() in ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP")
    }
    environment["PYTHONPATH"] = str(ROOT / "backend")
    environment.update(
        DATA_DIR=str(settings.storage),
        OCR_ENABLED=str(settings.ocr_enabled).lower(),
        OCR_MAX_PAGES=str(settings.ocr_max_pages),
        OCR_MIN_SCORE=str(settings.ocr_min_score),
        MAX_PAGES=str(settings.max_pages),
    )
    try:
        subprocess.run(
            [sys.executable, "-m", "app.parse_cli", str(settings.storage / key), str(output)],
            cwd=ROOT,
            env=environment,
            check=True,
            timeout=settings.parse_timeout,
            capture_output=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if output.stat().st_size > 8 * 1024 * 1024:
            raise ValueError("解析结果超过限制")
        parsed = json.loads(output.read_text(encoding="utf-8"))
    finally:
        output.unlink(missing_ok=True)
    with SessionLocal.begin() as db:
        r = locked_run(db, run_id, fence)
        case = db.scalar(select(Case).where(Case.id == r.case_id).with_for_update())
        doc = db.get(Document, r.payload["document_id"])
        if not doc or not doc.active:
            raise Cancelled()
        ensure_parse(db, doc)
        append_parse(db, doc, parsed, "ocr" if parsed.get("engine", "").startswith("RapidOCR") else "native")
        bump(db, case, "document.parsed", {"document_id": doc.id, "status": doc.parse_status})
        r.result = {"document_id": doc.id, "parse_status": doc.parse_status}


def process(run_id, fence, kind):
    stop = threading.Event()
    heartbeat_thread = threading.Thread(target=heartbeat, args=(run_id, fence, stop), daemon=True)
    heartbeat_thread.start()
    try:
        if kind == "parse":
            parse_task(run_id, fence)
        else:
            if kind == "check":
                with SessionLocal.begin() as db:
                    r = locked_run(db, run_id, fence)
                    if "findings" not in r.result:
                        r.result = {**r.result, **review_result(r.snapshot, run_checks(r.snapshot))}
            run_agent(run_id, fence)
        with SessionLocal.begin() as db:
            r = locked_run(db, run_id, fence)
            case = db.scalar(select(Case).where(Case.id == r.case_id).with_for_update())
            r.status = "waiting_for_input" if r.result.get("question") else "completed"
            r.updated_at = now()
            if r.result.get("findings"):
                if case.revision == r.revision:
                    current = db.get(Run, case.current_check_id) if case.current_check_id else None
                    if not current or current.created_at <= r.created_at:
                        case.current_check_id = r.id
                else:
                    r.result = {**r.result, "stale": True}
            if (
                r.result.get("findings")
                and case.current_check_id == r.id
                and case.revision == r.revision
                and checklist(db, case)["can_export"]
            ):
                synchronize_issues(db, case)
            event(db, r.id, "run.completed", {"status": r.status})
    except Cancelled:
        with SessionLocal.begin() as db:
            r = db.scalar(select(Run).where(Run.id == run_id).with_for_update())
            if r and r.fence == fence:
                r.status = "cancelled"
                r.updated_at = now()
                event(db, r.id, "run.cancelled")
    except Exception as error:
        # No raw network exceptions/SQL parameters: diagnostic details stay out of user responses.
        safe = (
            str(error)[:500]
            if isinstance(error, (ValueError, RuntimeError))
            else "任务执行失败，请重试或检查服务状态"
        )
        with SessionLocal.begin() as db:
            r = db.scalar(select(Run).where(Run.id == run_id).with_for_update())
            if r and r.fence == fence:
                r.status = "failed"
                r.error = safe
                r.updated_at = now()
                if r.result.get("findings"):
                    case = db.scalar(select(Case).where(Case.id == r.case_id).with_for_update())
                    current = db.get(Run, case.current_check_id) if case.current_check_id else None
                    if case.revision == r.revision and (not current or current.created_at <= r.created_at):
                        case.current_check_id = r.id
                if kind == "parse":
                    doc = db.get(Document, r.payload.get("document_id"))
                    if doc:
                        ensure_parse(db, doc)
                        append_parse(
                            db, doc, {"pages": doc.pages, "status": "failed", "note": safe}, "failed"
                        )
                db.add(
                    Message(
                        case_id=r.case_id,
                        run_id=r.id,
                        role="assistant",
                        content=f"本次任务未完全完成：{safe}。已完成的检查结果已保留。",
                    )
                )
                event(db, r.id, "run.failed", {"message": safe})
    finally:
        stop.set()
        heartbeat_thread.join(timeout=2)


def main():
    print("PacketPilot worker ready", flush=True)
    while True:
        task = claim()
        if task:
            process(*task)
        else:
            time.sleep(1)


if __name__ == "__main__":
    main()
