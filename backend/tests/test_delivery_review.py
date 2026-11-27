import hashlib
import io
import json
import zipfile

import pytest
from app.models import User
from argon2 import PasswordHasher
from test_workflow import activate_rule, case, check, current, text_document


def packet_body(client, item, doc, **changes):
    return {
        "revision": current(client, item)["revision"],
        "title": "合成交付包",
        "request_key": "request-one",
        "entries": [{"document_id": doc["id"], "path": "材料/01_申请表.txt", "content": "original"}],
        "acknowledge_warnings": True,
        **changes,
    }


def test_frozen_packet_has_real_bytes_and_stays_fixed_after_correction_and_unlink(client):
    item = case(client)
    doc = text_document(client, item, "申请表\n姓名：林沐\n申请类别：交流")
    path = f"/api/v1/cases/{item['id']}/packets"
    body = packet_body(client, item, doc)
    preview = client.post(path + "/preview", json=body)
    assert preview.status_code == 200 and preview.json()["warnings"]
    assert client.post(path, json={**body, "acknowledge_warnings": False}).status_code == 422
    response = client.post(path, json=body)
    assert response.status_code == 201, response.text
    packet = response.json()
    assert client.post(path, json=body).json()["id"] == packet["id"]
    assert client.post(path, json={**body, "title": "changed"}).status_code == 409
    downloaded = client.get(f"/api/v1/packets/{packet['id']}/download")
    assert hashlib.sha256(downloaded.content).hexdigest() == packet["sha256"]
    with zipfile.ZipFile(io.BytesIO(downloaded.content)) as z:
        assert z.namelist() == ["材料/01_申请表.txt", "manifest.json", "contents.txt"]
        manifest = json.loads(z.read("manifest.json"))
        original = z.read("材料/01_申请表.txt")
        assert original == "申请表\n姓名：林沐\n申请类别：交流".encode()
        assert hashlib.sha256(original).hexdigest() == manifest["entries"][0]["sha256"]
        assert "facts" not in manifest and "deliveries" not in manifest
    corrected = client.post(
        f"/api/v1/documents/{doc['id']}/page-corrections",
        json={
            "revision": current(client, item)["revision"],
            "parse_revision_id": doc["parse_revision_id"],
            "page": 1,
            "text": "申请表\n姓名：林沐二\n申请类别：交流",
            "confirm_page": True,
        },
    )
    assert corrected.status_code == 200, corrected.text
    assert client.get(path).json()[0]["changed"]
    assert client.get(path).json()[0]["diff"]["changed"] == [doc["id"]]
    assert client.request(
        "DELETE",
        f"/api/v1/case-document-links/{doc['id']}",
        json={"revision": current(client, item)["revision"]},
    ).is_success
    assert client.get(f"/api/v1/packets/{packet['id']}/download").content == downloaded.content
    assert client.get(path).json()[0]["delivery_status"] == "not_recorded"


@pytest.mark.parametrize(
    "name",
    [
        "../secret.txt",
        "/absolute.txt",
        "a//b.txt",
        "C:/file.txt",
        "CON.txt",
        "manifest.json",
        "a/../b.txt",
        "a\\..\\b.txt",
        "bad .txt.",
    ],
)
def test_packet_paths_are_portable_and_cannot_escape(client, name):
    item = case(client)
    d = text_document(client, item, "合成材料")
    body = packet_body(client, item, d, entries=[{"document_id": d["id"], "path": name}])
    assert client.post(f"/api/v1/cases/{item['id']}/packets", json=body).status_code == 422


def test_packet_scope_sources_duplicate_and_delivery_events(client, database):
    a, b = case(client), case(client)
    doc = text_document(client, a, "合成文件")
    source = text_document(client, a, "仅作为来源", purpose="source")
    assert (
        client.post(f"/api/v1/cases/{b['id']}/packets", json=packet_body(client, b, doc)).status_code == 409
    )
    path = f"/api/v1/cases/{a['id']}/packets"
    assert client.post(path, json=packet_body(client, a, source)).status_code == 409
    body = packet_body(client, a, doc)
    assert client.post(path, json={**body, "entries": body["entries"] * 2}).status_code == 422
    p = client.post(path, json=body).json()
    delivery = f"/api/v1/packets/{p['id']}/deliveries"
    event = {
        "status": "received",
        "channel": "人工上传平台",
        "recipient": "合成机构",
        "reference": "合成回执-1",
        "occurred_at": "2026-11-27T10:00:00+08:00",
    }
    assert client.post(delivery, json=event).status_code == 409
    assert (
        client.post(
            delivery, json={**event, "status": "submitted", "occurred_at": "2026-11-27T09:00:00"}
        ).status_code
        == 422
    )
    assert client.post(delivery, json={**event, "status": "submitted"}).status_code == 201
    assert (
        client.post(delivery, json={**event, "occurred_at": "2026-11-27T09:00:00+08:00"}).status_code == 422
    )
    received = client.post(delivery, json=event)
    assert received.status_code == 201 and len(received.json()["deliveries"]) == 2
    with database.begin() as db:
        db.add(User(username="foreign", password_hash=PasswordHasher().hash("synthetic-other-password")))
    client.post("/api/v1/auth/logout")
    client.post("/api/v1/auth/login", json={"username": "foreign", "password": "synthetic-other-password"})
    assert client.get(f"/api/v1/packets/{p['id']}/download").status_code == 404
    assert client.post(delivery, json=event).status_code == 404
    assert client.get(f"/api/v1/documents/{doc['id']}/parses").status_code == 404


def test_source_correction_pins_old_evidence_and_invalidates_active_rules(client):
    item = activate_rule(client, case(client))
    doc = text_document(client, item, "申请表\n姓名：林沐\n申请类别：交流")
    item = check(client, item)
    assert item["checklist"]["status"] == "ready"
    source = next(d for d in item["documents"] if d["purpose"] == "source")
    old = client.get(f"/api/v1/documents/{source['id']}").json()
    result = client.post(
        f"/api/v1/documents/{source['id']}/page-corrections",
        json={
            "revision": item["revision"],
            "parse_revision_id": old["parse_revision_id"],
            "page": 1,
            "text": "申请表须填写姓名及申请类别。",
            "confirm_page": True,
        },
    )
    assert result.status_code == 200
    assert (
        client.get(f"/api/v1/documents/{source['id']}?parse_revision_id={old['parse_revision_id']}").json()[
            "pages"
        ]
        == old["pages"]
    )
    assert current(client, item)["checklist"]["stale"]
    assert (
        client.post(
            f"/api/v1/cases/{item['id']}/checks/basic", json={"revision": current(client, item)["revision"]}
        ).status_code
        == 409
    )
    assert (
        client.get(f"/api/v1/documents/{doc['id']}?parse_revision_id={old['parse_revision_id']}").status_code
        == 404
    )


def test_field_correction_keeps_original_and_other_pages_unconfirmed(client, database):
    from app.application.parses import append_parse
    from app.models import Document

    item = case(client)
    doc = text_document(client, item, "姓名：林木\n岗位：开发")
    original = client.get(f"/api/v1/documents/{doc['id']}/content").content
    with database.begin() as db:
        d = db.get(Document, doc["id"])
        p = append_parse(
            db,
            d,
            {
                "status": "needs_review",
                "pages": [
                    {
                        "number": 1,
                        "label": "第一页",
                        "text": "姓名：林木",
                        "status": "needs_review",
                        "regions": [],
                    },
                    {"number": 2, "label": "第二页", "text": "", "status": "needs_review", "regions": []},
                ],
                "note": "合成部分结果",
            },
            "ocr",
        )
        parse_id = p.id
    result = client.post(
        f"/api/v1/documents/{doc['id']}/page-corrections",
        json={
            "revision": current(client, item)["revision"],
            "parse_revision_id": parse_id,
            "page": 1,
            "field_id": "1:0",
            "text": "林沐",
        },
    )
    assert result.status_code == 200, result.text
    assert result.json()["status"] == "needs_review" and result.json()["fields"][0]["confirmed"]
    assert len(client.get(f"/api/v1/documents/{doc['id']}/parses").json()["items"]) == 3
    assert client.get(f"/api/v1/documents/{doc['id']}/content").content == original
    assert (
        client.post(
            f"/api/v1/documents/{doc['id']}/page-corrections",
            json={
                "revision": current(client, item)["revision"],
                "parse_revision_id": parse_id,
                "page": 1,
                "text": "旧解析覆盖",
            },
        ).status_code
        == 409
    )


@pytest.mark.parametrize(
    "scenario",
    [
        "education_exchange",
        "job_application",
        "onboarding",
        "business_entry",
        "supplier_qualification",
        "research_grant",
        "competition_submission",
        "credential_renewal",
        "volunteer_application",
    ],
)
def test_all_scenario_packets_have_editable_output_and_frozen_delivery(client, scenario):
    item = case(client, scenario_id=scenario)
    assert item["scenario"]["slots"] and item["scenario"]["output"]["folder"] == scenario
    doc = text_document(client, item, "合成场景材料\n姓名：合成使用者")
    body = packet_body(
        client, item, doc, entries=[{"document_id": doc["id"], "path": f"{scenario}/01_材料.txt"}]
    )
    result = client.post(f"/api/v1/cases/{item['id']}/packets", json=body)
    assert result.status_code == 201
    assert result.json()["manifest"]["scenario"] == scenario
    assert not client.get(f"/api/v1/cases/{item['id']}/scenario-update").json()["available"]
