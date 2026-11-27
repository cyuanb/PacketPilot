import io
import json
import zipfile

import pytest
from PIL import Image
from test_workflow import case, current, text_document


def login(client, name="tester", password="test-password-123"):
    client.post("/api/v1/auth/logout")
    response = client.post("/api/v1/auth/login", json={"username": name, "password": password})
    assert response.is_success, response.text


def test_persistent_work_reminders_calendar_and_optimistic_edits(client):
    c = case(client)
    body = {
        "kind": "deadline",
        "title": "外部截止",
        "due_at": "2020-01-01T10:00:00+08:00",
        "timezone": "Asia/Shanghai",
        "note": "合成说明",
    }
    r = client.post(f"/api/v1/cases/{c['id']}/work", json=body)
    assert r.status_code == 201, r.text
    w = r.json()
    assert w["overdue"] and w["reminder"]
    assert client.get("/api/v1/reminders").json()[0]["id"] == w["id"]
    assert "20200101T020000Z" in client.get(f"/api/v1/cases/{c['id']}/calendar.ics").text
    assert client.put("/api/v1/work/" + w["id"], json={**body, "revision": 1, "status": "done"}).is_success
    assert (
        client.put("/api/v1/work/" + w["id"], json={**body, "revision": 1, "status": "todo"}).status_code
        == 409
    )
    assert client.get("/api/v1/reminders").json() == []
    assert len(client.get("/api/v1/work/" + w["id"] + "/history").json()) == 2
    assert (
        client.post(
            f"/api/v1/cases/{c['id']}/work", json={**body, "due_at": "2026-11-27T10:00:00"}
        ).status_code
        == 422
    )


@pytest.mark.parametrize("role", ["reader", "reviewer", "collector"])
def test_scoped_invitation_and_revocation_never_exposes_owner_endpoints(client, role):
    c = case(client)
    d = text_document(client, c, "申请表\n姓名：合成人")
    private = text_document(client, c, "不应共享的通知", "source")
    invite = client.post(
        f"/api/v1/cases/{c['id']}/invitations",
        json={"role": role, "document_ids": [] if role == "collector" else [d["id"]]},
    ).json()
    response = client.post(
        "/api/v1/invitations/accept",
        json={"token": invite["token"], "username": "collaborator", "password": "synthetic-password-123"},
    )
    assert response.is_success, response.text
    assert (
        client.post(
            "/api/v1/invitations/accept",
            json={"token": invite["token"], "username": "another", "password": "synthetic-password-123"},
        ).status_code
        == 404
    )
    login(client, "collaborator", "synthetic-password-123")
    assert client.get(f"/api/v1/cases/{c['id']}").status_code == 404
    assert client.get(f"/api/v1/documents/{d['id']}").status_code == 404
    assert client.get("/api/v1/shared/" + invite["id"]).is_success
    assert client.get(f"/api/v1/shared/{invite['id']}/documents/{private['id']}/content").status_code == 404
    expected = 404 if role == "collector" else 200
    assert client.get(f"/api/v1/shared/{invite['id']}/documents/{d['id']}/content").status_code == expected
    comment = {
        "document_id": d["id"],
        "parse_revision_id": d["parse_revision_id"],
        "page": 1,
        "quote": "姓名：合成人",
        "content": "合成复核意见",
        "decision": "approved",
    }
    assert client.post(f"/api/v1/shared/{invite['id']}/comments", json=comment).status_code == (
        201 if role == "reviewer" else 403
    )
    login(client)
    assert client.delete("/api/v1/invitations/" + invite["id"]).is_success
    login(client, "collaborator", "synthetic-password-123")
    assert client.get("/api/v1/shared/" + invite["id"]).status_code == 404
    assert client.get(f"/api/v1/shared/{invite['id']}/documents/{d['id']}/content").status_code == 404


def test_collection_requires_owner_acceptance_and_keeps_review_bound_to_version(client):
    c = case(client)
    g = client.post(f"/api/v1/cases/{c['id']}/invitations", json={"role": "collector"}).json()
    client.post(
        "/api/v1/invitations/accept",
        json={"token": g["token"], "username": "helper", "password": "synthetic-password-123"},
    )
    login(client, "helper", "synthetic-password-123")
    s = client.post(
        f"/api/v1/shared/{g['id']}/submissions",
        files={"file": ("application.txt", "申请表\n姓名：合成".encode())},
    )
    assert s.status_code == 201, s.text
    login(client)
    assert not current(client, c)["documents"]
    accepted = client.post(
        f"/api/v1/submissions/{s.json()['id']}/review", json={"decision": "accept", "category": "申请表"}
    )
    assert accepted.is_success, accepted.text
    assert len(current(client, c)["documents"]) == 1
    assert (
        client.post(f"/api/v1/submissions/{s.json()['id']}/review", json={"decision": "accept"}).status_code
        == 409
    )


def test_recovery_code_single_use_revokes_every_session(client, database):
    r = client.post("/api/v1/account/recovery-code", json={"password": "test-password-123"})
    assert r.is_success
    body = {
        "username": "tester",
        "recovery_code": r.json()["recovery_code"],
        "new_password": "changed-synthetic-password",
    }
    assert client.post("/api/v1/account/recover", json=body).is_success
    assert client.get("/api/v1/me").status_code == 401
    assert client.post("/api/v1/account/recover", json=body).status_code == 401
    login(client, "tester", "changed-synthetic-password")
    rows = client.get("/api/v1/account/sessions").json()
    assert len(rows) == 1 and rows[0]["current"]


def test_derivatives_preserve_originals_and_page_order(client):
    from pypdf import PdfReader

    c = case(client)
    buffer = io.BytesIO()
    Image.new("RGB", (300, 500), "red").save(buffer, "PNG")
    raw = buffer.getvalue()
    d = client.post(
        f"/api/v1/cases/{c['id']}/documents", files={"file": ("source.png", raw, "image/png")}
    ).json()["document"]
    result = client.post(
        f"/api/v1/cases/{c['id']}/derivatives",
        json={
            "revision": current(client, c)["revision"],
            "title": "组合",
            "operation": "pdf",
            "selections": [{"document_id": d["id"], "rotation": 90}, {"document_id": d["id"]}],
        },
    )
    assert result.status_code == 201, result.text
    output = client.get("/api/v1/documents/" + result.json()["document"]["id"] + "/content").content
    reader = PdfReader(io.BytesIO(output))
    assert len(reader.pages) == 2 and reader.pages[0].rotation == 90
    assert client.get("/api/v1/documents/" + d["id"] + "/content").content == raw


def test_backup_roundtrip_copies_data_and_files_without_grants_or_sessions(client):
    c = case(client)
    d = text_document(client, c, "申请表\n姓名：合成")
    client.post(
        f"/api/v1/cases/{c['id']}/work", json={"title": "持续任务", "kind": "draft", "note": "未完成的方案"}
    )
    backup = client.get("/api/v1/data/backup")
    assert backup.is_success, backup.text
    with zipfile.ZipFile(io.BytesIO(backup.content)) as z:
        data = json.loads(z.read("data.json"))
        assert "auth_sessions" not in data["tables"] and "access_grants" not in data["tables"]
    preview = client.post("/api/v1/data/restore-preview", files={"file": ("data.zip", backup.content)})
    assert preview.is_success, preview.text
    response = client.post("/api/v1/data/restore", files={"file": ("data.zip", backup.content)})
    assert response.is_success, response.text
    cases = client.get("/api/v1/cases").json()
    assert len(cases) == 2
    copied = next(v for v in cases if v["id"] != c["id"])
    copied = current(client, copied)
    assert copied["documents"][0]["id"] != d["id"]
    assert (
        client.get("/api/v1/documents/" + copied["documents"][0]["id"] + "/content").content
        == "申请表\n姓名：合成".encode()
    )
    assert client.get(f"/api/v1/cases/{copied['id']}/work").json()[0]["note"] == "未完成的方案"
    assert client.get("/api/v1/shared").json() == []


def test_permanent_purge_blocks_case_references(client):
    c = case(client)
    d = text_document(client, c, "合成原件")
    v = client.get("/api/v1/asset-revisions/" + d["asset_revision_id"]).json()
    a = client.get("/api/v1/assets/" + v["asset_id"]).json()
    updated = client.patch(
        "/api/v1/assets/" + a["id"], json={"revision": a["revision"], "title": a["title"], "archived": True}
    )
    assert updated.is_success, updated.text
    a = updated.json()
    assert (
        client.request(
            "DELETE", "/api/v1/assets/" + a["id"] + "/purge", json={"revision": a["revision"]}
        ).status_code
        == 409
    )
