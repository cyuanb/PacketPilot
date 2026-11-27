"""HTTP endpoints for reports."""

import html
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from ..application.cases import case_for, expect_revision
from ..application.issues import synchronize_issues
from ..application.reports import checklist
from ..db import get_db
from ..models import Attestation, Audit
from .dependencies import current_user
from .requests import AttestationInput

router = APIRouter()


@router.post("/api/v1/cases/{case_id}/attestations")
def attest(case_id: str, body: AttestationInput, user=Depends(current_user), db: Session = Depends(get_db)):
    c = case_for(db, user.id, case_id, True)
    expect_revision(c, body.revision)
    report = checklist(db, c)
    f = next((f for f in report["findings"] if f["requirement_id"] == body.requirement_id), None)
    if not f or f["method"] != "manual" or not report["can_export"] or f["applicability"] != "applicable":
        raise HTTPException(422, "仅可对当前版本的人工检查项确认")
    db.add(Attestation(case_id=c.id, revision=c.revision, requirement_id=body.requirement_id, note=body.note))
    db.add(Audit(case_id=c.id, action="manual.confirmed", data={"requirement_id": body.requirement_id}))
    db.flush()
    synchronize_issues(db, c)
    db.commit()
    return checklist(db, c)


@router.get("/api/v1/cases/{case_id}/export")
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
