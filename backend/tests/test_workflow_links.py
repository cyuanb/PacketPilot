from datetime import datetime, timezone

from app.models import Document, User
from argon2 import PasswordHasher
from test_workflow import activate_rule, case, check, current, text_document


def confirm(client, item, doc, confirmed=True):
    return client.post(
        f"/api/v1/documents/{doc['id']}/confirmation",
        json={
            "revision": current(client, item)["revision"],
            "parse_revision_id": doc["parse_revision_id"],
            "confirmed": confirmed,
        },
    )


def test_material_confirmation_is_distinct_idempotent_and_invalidated_by_parse(client):
    item = activate_rule(client, case(client))
    doc = text_document(client, item, "申请表\n姓名：待填写\n申请类别：交流")
    item = check(client, item)
    before = item["checklist"]["status"]
    revision = item["revision"]
    response = confirm(client, item, doc)
    assert response.is_success, response.text
    first = response.json()
    assert first["confirmation"]["state"] == "confirmed"
    assert "_confirmation" not in first["assignment"]
    assert (
        confirm(client, item, doc).json()["confirmation"]["confirmed_at"]
        == first["confirmation"]["confirmed_at"]
    )
    item = current(client, item)
    assert item["revision"] == revision and not item["checklist"]["stale"]
    assert item["checklist"]["status"] == before and before != "ready"
    edited = client.post(
        f"/api/v1/documents/{doc['id']}/page-corrections",
        json={
            "revision": revision,
            "parse_revision_id": doc["parse_revision_id"],
            "page": 1,
            "text": "申请表\n姓名：合成人\n申请类别：交流",
            "confirm_page": True,
        },
    )
    assert edited.is_success, edited.text
    d = client.get("/api/v1/documents/" + doc["id"]).json()
    assert d["confirmation"]["state"] == "stale"
    assert confirm(client, item, doc).status_code == 409
    assert confirm(client, item, d).json()["confirmation"]["state"] == "confirmed"
    assert confirm(client, item, d, False).json()["confirmation"]["state"] == "pending"
    assert confirm(client, item, d).is_success
    replacement = client.post(
        f"/api/v1/cases/{item['id']}/documents",
        data={"replace_id": d["id"]},
        files={"file": ("new.txt", b"new synthetic material")},
    )
    assert replacement.is_success
    assert replacement.json()["document"]["confirmation"]["state"] == "pending"
    assert confirm(client, item, d).status_code == 409


def test_assignment_changes_invalidate_review_and_keep_derivation(client, database):
    item = case(client)
    doc = text_document(client, item, "申请表\n姓名：合成\n申请类别：交流")
    with database.begin() as db:
        d = db.get(Document, doc["id"])
        d.assignment = {"derivation": [{"document_id": "synthetic-source"}]}
    assert confirm(client, item, doc).is_success
    response = client.put(
        f"/api/v1/documents/{doc['id']}/assignment",
        json={"revision": current(client, item)["revision"], "state": "accepted", "document_type": "申请表"},
    )
    assert response.is_success, response.text
    assert response.json()["assignment"]["derivation"] == [{"document_id": "synthetic-source"}]
    assert response.json()["confirmation"]["state"] == "stale"


def test_confirmation_does_not_mark_unreadable_material_as_parsed(client, database):
    item = case(client)
    doc = text_document(client, item, "合成扫描材料")
    with database.begin() as db:
        db.get(Document, doc["id"]).parse_status = "needs_review"
    response = confirm(client, item, doc)
    assert response.json()["confirmation"]["state"] == "confirmed"
    assert response.json()["parse_status"] == "needs_review"
    with database.begin() as db:
        db.add(
            User(username="foreign-review", password_hash=PasswordHasher().hash("synthetic-other-password"))
        )
    client.post("/api/v1/auth/logout")
    client.post(
        "/api/v1/auth/login", json={"username": "foreign-review", "password": "synthetic-other-password"}
    )
    assert (
        client.post(
            f"/api/v1/documents/{doc['id']}/confirmation",
            json={"revision": 1, "parse_revision_id": doc["parse_revision_id"]},
        ).status_code
        == 404
    )


def test_excluded_material_cannot_be_frozen_and_unconfirmed_warning_is_explicit(client):
    item = case(client)
    d = text_document(client, item, "申请表\n姓名：合成")

    def packet():
        return client.post(
            f"/api/v1/cases/{item['id']}/packets/preview",
            json={
                "revision": current(client, item)["revision"],
                "title": "合成包",
                "request_key": "preview",
                "entries": [{"document_id": d["id"], "path": "form.txt"}],
            },
        )

    assert any("尚未由本人确认" in w for w in packet().json()["warnings"])
    confirm(client, item, d)
    preview = packet().json()
    assert preview["entries"][0]["owner_review"] == "confirmed"
    assert not any("尚未由本人确认" in w for w in preview["warnings"])
    client.put(
        "/api/v1/documents/" + d["id"] + "/assignment",
        json={"revision": current(client, item)["revision"], "state": "rejected"},
    )
    assert packet().status_code == 409
    assert confirm(client, item, d).status_code == 409


def test_cancel_parse_and_retry_updates_case_and_rejects_duplicate_jobs(client):
    item = case(client)
    response = client.post(
        f"/api/v1/cases/{item['id']}/documents", files={"file": ("material.txt", b"synthetic material")}
    )
    doc = response.json()["document"]
    run = response.json()["run_id"]
    before = current(client, item)["revision"]
    assert client.post("/api/v1/runs/" + run + "/cancel").is_success
    assert client.get("/api/v1/documents/" + doc["id"]).json()["parse_status"] == "needs_review"
    cancelled_revision = current(client, item)["revision"]
    assert cancelled_revision > before
    retry = client.post("/api/v1/runs/" + run + "/retry")
    assert retry.status_code == 202, retry.text
    assert current(client, item)["revision"] > cancelled_revision
    assert client.post("/api/v1/runs/" + run + "/retry").status_code == 409


def test_satisfied_any_group_closes_unused_child_issue_without_passing_it(client):
    item = case(client)
    source = text_document(client, item, "申请表或成绩单任选一份。", "source", "通知")
    evidence = [{"document_id": source["id"], "page": 1, "quote": "申请表或成绩单任选一份。"}]
    rules = [
        {
            "id": "a",
            "title": "申请表",
            "kind": "material_presence",
            "document_type": "申请表",
            "source_evidence": evidence,
        },
        {
            "id": "b",
            "title": "成绩单",
            "kind": "material_presence",
            "document_type": "成绩单",
            "source_evidence": evidence,
        },
        {
            "id": "g",
            "title": "任选一份",
            "kind": "group",
            "parameters": {"children": ["a", "b"], "operator": "any"},
            "source_evidence": evidence,
        },
    ]
    rev = current(client, item)["revision"]
    draft = client.post(
        f"/api/v1/cases/{item['id']}/rule-sets", json={"revision": rev, "requirements": rules}
    ).json()
    assert client.post("/api/v1/rule-sets/" + draft["id"] + "/activate", json={"revision": rev}).is_success
    check(client, item)
    text_document(client, item, "申请表\n姓名：合成\n申请类别：交流")
    report = check(client, item)
    assert report["checklist"]["status"] == "ready"
    issue = next(
        i
        for i in client.get(f"/api/v1/cases/{item['id']}/issues").json()["items"]
        if i["requirement_id"] == "b"
    )
    assert issue["status"] == "resolved" and issue["verdict"] == "missing"
    assert "无需继续补件" in issue["reason"]


def test_case_deadline_is_connected_to_reminders_and_date_only_calendar(client, monkeypatch):
    from app.api import planning

    monkeypatch.setattr(planning, "now", lambda: datetime(2026, 11, 28, 2, tzinfo=timezone.utc))
    item = client.post("/api/v1/cases", json={"title": "合成期限", "deadline": "2026-11-29"}).json()
    reminders = client.get("/api/v1/reminders").json()
    row = next(v for v in reminders if v["id"] == item["id"] + "-deadline")
    assert not row["overdue"] and row["kind"] == "case_deadline"
    calendar = client.get(f"/api/v1/cases/{item['id']}/calendar.ics").text
    assert "DTSTART;VALUE=DATE:20261129" in calendar and "235959" not in calendar


def test_rule_attestation_can_be_revoked_and_issue_reopens(client):
    item = activate_rule(client, case(client), kind="manual_review")
    text_document(client, item, "申请表\n姓名：合成\n申请类别：交流")
    item = check(client, item)
    response = client.post(
        f"/api/v1/cases/{item['id']}/attestations",
        json={"revision": item["revision"], "requirement_id": "name", "note": "合成样例已看原件"},
    )
    assert response.is_success and response.json()["status"] == "ready"
    response = client.request(
        "DELETE", f"/api/v1/cases/{item['id']}/attestations/name", json={"revision": item["revision"]}
    )
    assert response.is_success and response.json()["status"] == "needs_review"
    issue = client.get(f"/api/v1/cases/{item['id']}/issues").json()["items"][0]
    assert issue["status"] == "open" and issue["verdict"] == "unknown"
