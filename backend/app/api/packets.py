from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session, defer

from ..application.cases import case_for, expect_revision
from ..application.packets import freeze_packet, packet_view, packets_for, prepare_packet
from ..db import get_db
from ..models import DeliveryRecord, MaterialPacket
from ..schemas import RevisionInput, StrictModel
from .dependencies import current_user

router = APIRouter()


class PacketEntry(StrictModel):
    document_id: str = Field(max_length=36)
    path: str = Field(min_length=1, max_length=200)
    content: Literal["original", "parsed_text"] = "original"


class PacketInput(RevisionInput):
    title: str = Field(min_length=1, max_length=200)
    entries: list[PacketEntry] = Field(min_length=1, max_length=30)
    request_key: str = Field(min_length=1, max_length=100)
    acknowledge_warnings: bool = False


class DeliveryInput(StrictModel):
    status: Literal["submitted", "received", "returned"]
    channel: str = Field(min_length=1, max_length=200)
    recipient: str = Field(min_length=1, max_length=200)
    reference: str = Field(default="", max_length=500)
    note: str = Field(default="", max_length=2000)
    occurred_at: datetime

    @field_validator("occurred_at")
    @classmethod
    def timezone_required(cls, value):
        if value.tzinfo is None:
            raise ValueError("交付时间必须包含时区")
        return value


def owned_packet(db, user, identifier, lock=False):
    p = db.scalar(
        select(MaterialPacket).options(defer(MaterialPacket.archive)).where(MaterialPacket.id == identifier)
    )
    if not p:
        raise HTTPException(404, "材料包不存在")
    case = case_for(db, user.id, p.case_id, lock)
    return p, case


@router.get("/api/v1/cases/{case_id}/packets")
def list_packets(case_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    return packets_for(db, case_for(db, user.id, case_id))


@router.post("/api/v1/cases/{case_id}/packets/preview")
def preview_packet(
    case_id: str, body: PacketInput, user=Depends(current_user), db: Session = Depends(get_db)
):
    c = case_for(db, user.id, case_id, True)
    expect_revision(c, body.revision)
    entries, _, warnings, _ = prepare_packet(db, c, body)
    return {"entries": entries, "warnings": warnings}


@router.post("/api/v1/cases/{case_id}/packets", status_code=201)
def create_packet(case_id: str, body: PacketInput, user=Depends(current_user), db: Session = Depends(get_db)):
    c = case_for(db, user.id, case_id, True)
    p = freeze_packet(db, c, body)
    db.commit()
    return packet_view(db, p, c)


@router.get("/api/v1/packets/{packet_id}/download")
def download_packet(packet_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    p, _ = owned_packet(db, user, packet_id)
    return Response(
        bytes(p.archive),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="packet-{p.id}.zip"',
            "X-Content-SHA256": p.sha256,
        },
    )


@router.post("/api/v1/packets/{packet_id}/deliveries", status_code=201)
def record_delivery(
    packet_id: str, body: DeliveryInput, user=Depends(current_user), db: Session = Depends(get_db)
):
    p, c = owned_packet(db, user, packet_id, True)
    previous = db.scalar(
        select(DeliveryRecord)
        .where(DeliveryRecord.packet_id == p.id)
        .order_by(DeliveryRecord.created_at.desc())
        .limit(1)
    )
    if body.status != "submitted" and (not previous or previous.status == "returned"):
        raise HTTPException(409, "先记录提交，再记录收到或退回")
    if previous and body.occurred_at < previous.occurred_at:
        raise HTTPException(422, "事件时间不能早于上一条交付记录")
    if body.status in ("received", "returned") and not (body.reference.strip() or body.note.strip()):
        raise HTTPException(422, "请填写回执编号或接收/退回说明")
    db.add(DeliveryRecord(packet_id=p.id, **body.model_dump()))
    db.commit()
    return packet_view(db, p, c)
