from datetime import timedelta

import pytest
from app.agent import Cancelled, execute_tool
from app.db import now
from app.models import Run, ToolCall, User
from app.worker import claim
from argon2 import PasswordHasher
from sqlalchemy import func, select


def demo(client):
    r = client.post("/api/v1/demo")
    assert r.status_code == 201, r.text
    return r.json()


def test_full_case_and_stale_export(client):
    c = demo(client)
    assert c["checklist"]["status"] == "blocked"
    assert len(c["checklist"]["findings"]) == 5
    assert client.get("/api/v1/cases/" + c["id"] + "/export").status_code == 200
    r = client.post(
        "/api/v1/cases/" + c["id"] + "/facts/confirm",
        json={"revision": c["revision"], "facts": {"申请类别": "硕士"}},
    )
    assert r.json()["checklist"]["stale"] is True
    assert client.get("/api/v1/cases/" + c["id"] + "/export").status_code == 409
    assert (
        client.post("/api/v1/cases/" + c["id"] + "/checks", json={"revision": c["revision"]}).status_code
        == 409
    )


def test_request_idempotency_and_body_conflict(client, database):
    c = demo(client)
    path = "/api/v1/cases/" + c["id"] + "/messages"
    headers = {"Idempotency-Key": "same-request"}
    body = {"revision": c["revision"], "text": "检查一下"}
    a, b = client.post(path, json=body, headers=headers), client.post(path, json=body, headers=headers)
    assert a.status_code == 202 and a.json()["id"] == b.json()["id"]
    assert client.post(path, json={**body, "text": "另一个请求"}, headers=headers).status_code == 409


def test_foreign_resources_and_csrf(client, database):
    c = demo(client)
    with database.begin() as db:
        u = User(username="other", password_hash=PasswordHasher().hash("other-password"))
        db.add(u)
    client.post("/api/v1/auth/logout")
    client.post("/api/v1/auth/login", json={"username": "other", "password": "other-password"})
    assert client.get("/api/v1/cases/" + c["id"]).status_code == 404
    assert client.get("/api/v1/documents/" + c["documents"][0]["id"]).status_code == 404
    assert client.get("/api/v1/runs/" + c["runs"][0]["id"]).status_code == 404
    assert client.get("/api/v1/runs/" + c["runs"][0]["id"] + "/events").status_code == 404
    assert client.post("/api/v1/demo", headers={"Origin": "https://attacker.invalid"}).status_code == 403


def test_file_upload_limits_and_immutable_correction(client):
    c = demo(client)
    path = "/api/v1/cases/" + c["id"] + "/documents"
    assert client.post(path, files={"file": ("payload.html", b"<script/>")}).status_code == 415
    d = next(d for d in c["documents"] if d["purpose"] == "material")
    changed = client.post(
        "/api/v1/documents/" + d["id"] + "/correction",
        json={"revision": c["revision"], "text": "申请表\n姓名：李沐"},
    )
    assert changed.status_code == 200
    assert changed.json()["id"] != d["id"] and changed.json()["version"] == 2
    assert client.get("/api/v1/documents/" + d["id"]).json()["active"] is False
    assert client.get("/api/v1/cases/" + c["id"]).json()["checklist"]["stale"]


def test_forged_requirement_source_rejected(client):
    c = demo(client)
    rule = c["checklist"]["requirements"][0]
    rule["source_evidence"][0]["quote"] = "不存在的要求"
    response = client.post(
        "/api/v1/cases/" + c["id"] + "/rule-sets", json={"revision": c["revision"], "requirements": [rule]}
    )
    assert response.status_code == 422


def test_requirement_activation_stales_check(client):
    c = demo(client)
    r = client.post(
        "/api/v1/cases/" + c["id"] + "/rule-sets",
        json={"revision": c["revision"], "requirements": c["checklist"]["requirements"]},
    ).json()
    response = client.post("/api/v1/rule-sets/" + r["id"] + "/activate", json={"revision": c["revision"]})
    assert response.status_code == 200 and response.json()["checklist"]["stale"]


def test_expired_worker_cannot_write(client, database):
    c = demo(client)
    r = client.post("/api/v1/cases/" + c["id"] + "/checks", json={"revision": c["revision"]}).json()
    first = claim()
    with database.begin() as db:
        db.get(Run, r["id"]).lease_until = now() - timedelta(seconds=1)
    second = claim()
    assert first[0] == second[0] and first[1] < second[1]
    with pytest.raises(Cancelled):
        execute_tool(first[0], first[1], "run_checks", {})
    a = execute_tool(second[0], second[1], "run_checks", {})
    b = execute_tool(second[0], second[1], "run_checks", {})
    assert a == b
    with database() as db:
        assert db.scalar(select(func.count()).select_from(ToolCall).where(ToolCall.run_id == r["id"])) == 1


def test_tool_document_scope_and_truncation(client, database):
    c = demo(client)
    r = client.post("/api/v1/cases/" + c["id"] + "/checks", json={"revision": c["revision"]}).json()
    task = claim()
    with pytest.raises(ValueError):
        execute_tool(task[0], task[1], "read_document", {"document_id": "not-in-this-case"})
    with database.begin() as db:
        run = db.get(Run, r["id"])
        import copy

        snap = copy.deepcopy(run.snapshot)
        snap["documents"][0]["pages"] = [{"number": 1, "label": "全文", "text": "甲" * 7000}]
        run.snapshot = snap
    out = execute_tool(task[0], task[1], "read_document", {"document_id": c["documents"][0]["id"]})
    assert out["has_more"] is True and out["next_offset"] == 6000
    tail = execute_tool(
        task[0], task[1], "read_document", {"document_id": c["documents"][0]["id"], "offset": 6000}
    )
    assert tail["has_more"] is False and len(tail["segments"][0]["text"]) == 1000


def test_cancel_prevents_tool_side_effect(client, database):
    c = demo(client)
    r = client.post("/api/v1/cases/" + c["id"] + "/checks", json={"revision": c["revision"]}).json()
    task = claim()
    assert client.post("/api/v1/runs/" + r["id"] + "/cancel").status_code == 200
    with pytest.raises(Cancelled):
        execute_tool(task[0], task[1], "run_checks", {})


def test_delete_source_invalidates_rules_and_history(client):
    c = demo(client)
    source = next(d for d in c["documents"] if d["purpose"] == "source")
    assert client.delete("/api/v1/documents/" + source["id"]).status_code == 200
    updated = client.get("/api/v1/cases/" + c["id"]).json()
    assert updated["checklist"]["status"] == "not_ready"
    assert client.get("/api/v1/documents/" + source["id"] + "/content").status_code == 404


def test_case_deletion_cascades(client, database):
    c = demo(client)
    assert client.delete("/api/v1/cases/" + c["id"]).status_code == 200
    assert client.get("/api/v1/cases/" + c["id"]).status_code == 404
    with database() as db:
        assert db.scalar(select(func.count()).select_from(Run).where(Run.case_id == c["id"])) == 0


def test_replacing_notice_requires_new_rules(client):
    c = demo(client)
    source = next(d for d in c["documents"] if d["purpose"] == "source")
    assert (
        client.post(
            "/api/v1/documents/" + source["id"] + "/correction",
            json={"revision": c["revision"], "text": "新通知：不再需要推荐信"},
        ).status_code
        == 200
    )
    updated = client.get("/api/v1/cases/" + c["id"]).json()
    assert updated["checklist"]["stale"]
    assert (
        client.post(
            "/api/v1/cases/" + c["id"] + "/checks", json={"revision": updated["revision"]}
        ).status_code
        == 409
    )
