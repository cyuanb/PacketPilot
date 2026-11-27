"""Persistent business work, reminders and user-reviewed suggestions."""

from datetime import datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..application.cases import case_for
from ..db import get_db, now
from ..models import Case, WorkEvent, WorkItem
from ..schemas import StrictModel
from .dependencies import current_user

router = APIRouter()


class WorkInput(StrictModel):
    kind: Literal["task", "question", "suggestion", "deadline", "expiry", "draft"] = "task"
    title: str = Field(min_length=1, max_length=200)
    status: Literal["todo", "doing", "waiting", "done", "dismissed"] = "todo"
    note: str = Field(default="", max_length=10000)
    due_at: datetime | None = None
    timezone: str = Field(default="Asia/Shanghai", max_length=60)
    reminder_minutes: int = Field(default=1440, ge=0, le=525600)
    revision: int | None = None


def validate(body):
    try:
        ZoneInfo(body.timezone)
    except ZoneInfoNotFoundError as error:
        raise HTTPException(422, "请选择有效时区") from error
    if body.due_at and body.due_at.tzinfo is None:
        raise HTTPException(422, "期限必须包含明确时区")
    if body.kind in ("deadline", "expiry") and not body.due_at:
        raise HTTPException(422, "期限和资料到期需要明确日期时间")


def view(item):
    due = datetime.fromisoformat(item.detail["due_at"]) if item.detail.get("due_at") else None
    return {
        "id": item.id,
        "case_id": item.case_id,
        "kind": item.kind,
        "title": item.title,
        "status": item.status,
        "revision": item.revision,
        **item.detail,
        "reminder": bool(
            due
            and item.status not in ("done", "dismissed")
            and now() >= due - timedelta(minutes=item.detail.get("reminder_minutes", 1440))
        ),
        "overdue": bool(due and now() > due and item.status not in ("done", "dismissed")),
        "updated_at": item.updated_at.isoformat(),
    }


@router.get("/api/v1/cases/{case_id}/work")
def list_work(case_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    case_for(db, user.id, case_id)
    return [
        view(w)
        for w in db.scalars(select(WorkItem).where(WorkItem.case_id == case_id).order_by(WorkItem.created_at))
    ]


@router.post("/api/v1/cases/{case_id}/work", status_code=201)
def create_work(case_id: str, body: WorkInput, user=Depends(current_user), db: Session = Depends(get_db)):
    case_for(db, user.id, case_id, True)
    validate(body)
    item = WorkItem(
        case_id=case_id,
        kind=body.kind,
        title=body.title,
        status=body.status,
        detail=body.model_dump(mode="json", exclude={"revision", "kind", "title", "status"}),
    )
    db.add(item)
    db.flush()
    db.add(WorkEvent(item_id=item.id, actor_id=user.id, data={"action": "created", "status": body.status}))
    db.commit()
    return view(item)


@router.put("/api/v1/work/{item_id}")
def edit_work(item_id: str, body: WorkInput, user=Depends(current_user), db: Session = Depends(get_db)):
    item = db.get(WorkItem, item_id)
    if not item:
        raise HTTPException(404, "任务不存在")
    case_for(db, user.id, item.case_id, True)
    db.refresh(item)
    if item.revision != body.revision:
        raise HTTPException(409, "任务已更新，请刷新")
    validate(body)
    db.add(
        WorkEvent(
            item_id=item.id,
            actor_id=user.id,
            data={
                "action": "updated",
                "previous_status": item.status,
                "status": body.status,
                "note": body.note,
            },
        )
    )
    item.title, item.kind, item.status = body.title, body.kind, body.status
    item.detail = body.model_dump(mode="json", exclude={"revision", "kind", "title", "status"})
    item.revision += 1
    item.updated_at = now()
    db.commit()
    return view(item)


@router.get("/api/v1/work/{item_id}/history")
def work_history(item_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    item = db.get(WorkItem, item_id)
    if not item:
        raise HTTPException(404, "任务不存在")
    case_for(db, user.id, item.case_id)
    return [
        {"at": e.created_at.isoformat(), **e.data}
        for e in db.scalars(
            select(WorkEvent).where(WorkEvent.item_id == item.id).order_by(WorkEvent.created_at)
        )
    ]


@router.post("/api/v1/cases/{case_id}/work/suggest")
def suggest_work(case_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    from ..application.reports import checklist

    c = case_for(db, user.id, case_id, True)
    existing = {
        w.detail.get("suggestion_key") for w in db.scalars(select(WorkItem).where(WorkItem.case_id == c.id))
    }
    for finding in checklist(db, c)["findings"]:
        key = f"{c.revision}:{finding['requirement_id']}"
        if (
            finding["verdict"] != "pass"
            and finding["applicability"] != "not_applicable"
            and key not in existing
        ):
            db.add(
                WorkItem(
                    case_id=c.id,
                    kind="suggestion",
                    title=finding["next_action"][:200] or "核对待解决要求",
                    detail={
                        "note": finding["reason"],
                        "suggestion_key": key,
                        "based_on_revision": c.revision,
                    },
                )
            )
    db.commit()
    return list_work(case_id, user, db)


@router.get("/api/v1/reminders")
def reminders(user=Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(WorkItem)
        .join(Case, Case.id == WorkItem.case_id)
        .where(Case.owner_id == user.id, ~Case.archived)
    )
    return [v for w in rows if (v := view(w))["reminder"]]


@router.get("/api/v1/cases/{case_id}/calendar.ics")
def calendar(case_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    from datetime import timezone

    def escape(value):
        return (
            str(value)
            .replace("\\", "\\\\")
            .replace("\r", "")
            .replace("\n", "\\n")
            .replace(";", "\\;")
            .replace(",", "\\,")
        )

    items = list_work(case_id, user, db)
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//PacketPilot//Calendar//ZH"]
    for item in items:
        if not item.get("due_at") or item["status"] == "dismissed":
            continue
        stamp = datetime.fromisoformat(item["due_at"]).astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        lines += [
            "BEGIN:VEVENT",
            f"UID:{item['id']}@packetpilot",
            "DTSTAMP:" + now().strftime("%Y%m%dT%H%M%SZ"),
            "DTSTART:" + stamp,
            "SUMMARY:" + escape(item["title"]),
            "DESCRIPTION:" + escape(item.get("note", "")),
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    return Response(
        "\r\n".join(lines) + "\r\n",
        media_type="text/calendar",
        headers={"Content-Disposition": 'attachment; filename="packetpilot.ics"'},
    )
