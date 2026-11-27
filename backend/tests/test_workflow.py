import pytest
from app.models import CaseDocumentLink, User
from app.worker import claim, process
from argon2 import PasswordHasher
from sqlalchemy.exc import IntegrityError


def case(client, title="合成事项", scenario_id=None):
    response = client.post("/api/v1/cases", json={"title": title, "scenario_id": scenario_id})
    assert response.status_code == 201, response.text
    return response.json()


def current(client, item):
    return client.get("/api/v1/cases/" + item["id"]).json()


def text_document(client, item, content, purpose="material", category="申请表"):
    response = client.post(
        f"/api/v1/cases/{item['id']}/sources/text",
        json={"title": category, "purpose": purpose, "category": category, "text": content},
    )
    assert response.status_code == 201, response.text
    return response.json()


def activate_rule(client, item, kind="required_field"):
    source = text_document(client, item, "申请表须填写姓名。", purpose="source", category="通知")
    rule = {
        "id": "name",
        "title": "申请表姓名",
        "kind": kind,
        "document_type": "申请表",
        "parameters": {"field": "姓名"},
        "source_evidence": [{"document_id": source["id"], "page": 1, "quote": "申请表须填写姓名。"}],
    }
    item = current(client, item)
    draft = client.post(
        f"/api/v1/cases/{item['id']}/rule-sets", json={"revision": item["revision"], "requirements": [rule]}
    )
    assert draft.status_code == 200, draft.text
    response = client.post(
        f"/api/v1/rule-sets/{draft.json()['id']}/activate", json={"revision": item["revision"]}
    )
    assert response.status_code == 200, response.text
    return response.json()


def check(client, item):
    item = current(client, item)
    response = client.post(f"/api/v1/cases/{item['id']}/checks/basic", json={"revision": item["revision"]})
    assert response.status_code == 200, response.text
    return response.json()


def test_two_cases_pin_versions_accept_update_separately_and_unlink_keeps_original(client, database):
    a, b = case(client, "项目甲"), case(client, "项目乙")
    doc = text_document(client, a, "申请表\n姓名：林沐\n申请类别：交流")
    version = client.get("/api/v1/asset-revisions/" + doc["asset_revision_id"]).json()
    linked = client.post(
        f"/api/v1/cases/{b['id']}/document-links",
        json={"revision": b["revision"], "asset_revision_id": version["id"], "category": "申请表"},
    )
    assert linked.status_code == 201, linked.text
    b = linked.json()
    b_doc = b["documents"][0]
    assert b_doc["id"] != doc["id"]
    asset = client.get("/api/v1/assets/" + version["asset_id"]).json()
    new = client.post(
        f"/api/v1/assets/{asset['id']}/versions",
        data={"revision": asset["revision"]},
        files={"file": ("new.txt", "申请表\n姓名：林沐二\n申请类别：交流".encode())},
    ).json()["asset"]
    assert current(client, b)["revision"] == b["revision"]
    assert current(client, a)["document_links"][0]["update_available"]
    a = current(client, a)
    response = client.post(
        f"/api/v1/documents/{doc['id']}/library-version",
        json={"revision": a["revision"], "asset_revision_id": new["latest"]["id"]},
    )
    assert response.status_code == 200, response.text
    task = claim()
    assert task[2] == "parse"
    process(*task)
    assert current(client, a)["document_links"][0]["version"] == 2
    assert current(client, b)["document_links"][0]["version"] == 1
    assert "林沐二" not in client.get(f"/api/v1/documents/{b_doc['id']}/content").text
    assert (
        client.request(
            "DELETE", f"/api/v1/case-document-links/{b_doc['id']}", json={"revision": b["revision"]}
        ).status_code
        == 200
    )
    assert client.get("/api/v1/asset-revisions/" + version["id"] + "/content").is_success
    assert current(client, a)["documents"]
    with database() as db:
        assert db.get(CaseDocumentLink, b_doc["id"]) is None


def test_linked_case_correction_appends_original_asset_without_updating_other_case(client):
    a, b = case(client), case(client)
    doc = text_document(client, a, "申请表\n姓名：林沐")
    version = client.get("/api/v1/asset-revisions/" + doc["asset_revision_id"]).json()
    b = client.post(
        f"/api/v1/cases/{b['id']}/document-links",
        json={"revision": b["revision"], "asset_revision_id": version["id"]},
    ).json()
    b_doc = b["documents"][0]
    changed = client.post(
        f"/api/v1/documents/{b_doc['id']}/correction",
        json={"revision": b["revision"], "text": "申请表\n姓名：已校订"},
    )
    assert changed.status_code == 200, changed.text
    asset = client.get("/api/v1/assets/" + version["asset_id"]).json()
    assert len(asset["versions"]) == 2
    assert current(client, a)["document_links"][0]["version"] == 1
    assert current(client, b)["document_links"][0]["version"] == 2
    assert "已校订" not in client.get("/api/v1/documents/" + changed.json()["id"] + "/content").text


def test_link_scope_conflicts_and_database_ownership(client, database):
    a = case(client)
    doc = text_document(client, a, "申请表\n姓名：示例")
    a = check(client, activate_rule(client, a, kind="manual_review"))
    own_issue = client.get(f"/api/v1/cases/{a['id']}/issues").json()["items"][0]
    with database.begin() as db:
        db.add(User(username="other", password_hash=PasswordHasher().hash("other-password")))
    client.post("/api/v1/auth/logout")
    client.post("/api/v1/auth/login", json={"username": "other", "password": "other-password"})
    b = case(client)
    assert client.get(f"/api/v1/issues/{own_issue['id']}/events").status_code == 404
    assert (
        client.patch(
            f"/api/v1/issues/{own_issue['id']}",
            json={"revision": a["revision"], "issue_revision": own_issue["revision"], "status": "requested"},
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/v1/cases/{b['id']}/document-links",
            json={"revision": b["revision"], "asset_revision_id": doc["asset_revision_id"]},
        ).status_code
        == 404
    )
    assert client.get(f"/api/v1/cases/{a['id']}/document-links").status_code == 404
    b_doc = text_document(client, b, "申请表\n姓名：另一个")
    with pytest.raises(IntegrityError), database.begin() as db:
        db.get(CaseDocumentLink, b_doc["id"]).workspace_id = a["workspace_id"]
    b = current(client, b)
    assert (
        client.post(
            f"/api/v1/cases/{b['id']}/document-links",
            json={"revision": b["revision"], "asset_revision_id": b_doc["asset_revision_id"]},
        ).status_code
        == 409
    )
    assert (
        client.request(
            "DELETE", f"/api/v1/case-document-links/{b_doc['id']}", json={"revision": b["revision"] - 1}
        ).status_code
        == 409
    )


@pytest.mark.parametrize(
    "identifier,kind",
    [
        ("education_exchange", "person"),
        ("job_application", "person"),
        ("onboarding", "person"),
        ("business_entry", "organization"),
        ("supplier_qualification", "organization"),
    ],
)
def test_scenarios_are_distinct_snapshots_with_scoped_primary_roles(client, identifier, kind):
    configs = client.get("/api/v1/scenarios").json()
    assert len(configs) == 5 and {c["family"] for c in configs} == {"education", "employment", "business"}
    item = case(client, scenario_id=identifier)
    assert item["scenario"]["id"] == identifier and item["scenario"]["support_level"] == "starter"
    item = activate_rule(client, item)
    assert (
        client.post(
            f"/api/v1/cases/{item['id']}/checks/basic", json={"revision": item["revision"]}
        ).status_code
        == 422
    )
    wrong = client.post(
        "/api/v1/subjects",
        json={"kind": "person" if kind == "organization" else "organization", "name": "错误类型"},
    ).json()
    path = f"/api/v1/cases/{item['id']}/subjects"
    assert (
        client.put(
            path,
            json={"revision": item["revision"], "links": [{"subject_id": wrong["id"], "role": "applicant"}]},
        ).status_code
        == 422
    )
    right = client.post("/api/v1/subjects", json={"kind": kind, "name": "正确主体"}).json()
    assert (
        client.put(
            path,
            json={"revision": item["revision"], "links": [{"subject_id": right["id"], "role": "applicant"}]},
        ).status_code
        == 200
    )
    assert check(client, item)["checklist"]["status"] == "blocked"


def test_issue_amendment_flow_only_current_checks_resolve_and_reopen(client):
    item = activate_rule(client, case(client))
    item = check(client, item)
    path = f"/api/v1/cases/{item['id']}/issues"
    issue = client.get(path).json()["items"][0]
    for state in ("requested", "submitted"):
        response = client.patch(
            "/api/v1/issues/" + issue["id"],
            json={
                "revision": item["revision"],
                "issue_revision": issue["revision"],
                "status": state,
                "note": "已联系申请人",
            },
        )
        assert response.status_code == 200, response.text
        issue = response.json()["items"][0]
        assert issue["status"] == state
    assert (
        client.patch(
            "/api/v1/issues/" + issue["id"],
            json={"revision": item["revision"], "issue_revision": issue["revision"], "status": "resolved"},
        ).status_code
        == 422
    )
    check(client, item)
    assert client.get(path).json()["items"][0]["status"] == "open"
    document = text_document(client, item, "申请表\n姓名：林沐")
    assert client.get(path).json()["items"][0]["stale"]
    item = current(client, item)
    assert client.post(path + "/sync", json={"revision": item["revision"]}).status_code == 409
    item = check(client, item)
    resolved = client.get(path).json()["items"][0]
    assert resolved["status"] == "resolved" and not resolved["stale"]
    assert (
        client.post(
            f"/api/v1/documents/{document['id']}/correction",
            json={"revision": item["revision"], "text": "申请表\n姓名：待填写"},
        ).status_code
        == 200
    )
    check(client, item)
    reopened = client.get(path).json()["items"][0]
    assert reopened["id"] == resolved["id"] and reopened["status"] == "open"
    assert any(
        event["action"] == "reopened"
        for event in client.get(f"/api/v1/issues/{resolved['id']}/events").json()
    )


def test_exception_is_not_a_pass_and_expires_on_recheck(client):
    item = check(client, activate_rule(client, case(client)))
    path = f"/api/v1/cases/{item['id']}/issues"
    issue = client.get(path).json()["items"][0]
    payload = {"revision": item["revision"], "issue_revision": issue["revision"], "status": "exception"}
    assert client.patch("/api/v1/issues/" + issue["id"], json=payload).status_code == 422
    assert (
        client.patch(
            "/api/v1/issues/" + issue["id"], json={**payload, "note": "本人记录例外，不代表接收方认可"}
        ).status_code
        == 200
    )
    assert current(client, item)["checklist"]["status"] == "blocked"
    check(client, item)
    assert client.get(path).json()["items"][0]["status"] == "open"


@pytest.mark.parametrize(
    "scene,subject_kind,material,field,value",
    [
        ("education_exchange", "person", "成绩单", "姓名", "合成学生"),
        ("job_application", "person", "简历", "姓名", "合成求职者"),
        ("onboarding", "person", "入职登记表", "岗位", "研发实习"),
        ("business_entry", "organization", "营业执照", "统一社会信用代码", "SYNTHETIC-ONLY"),
        ("supplier_qualification", "organization", "供应商问卷", "供货类别", "合成办公用品"),
    ],
)
def test_each_scenario_links_its_material_and_resolves_its_requirement(
    client, scene, subject_kind, material, field, value
):
    item = case(client, scenario_id=scene)
    owner = client.post("/api/v1/subjects", json={"kind": subject_kind, "name": "合成主体"}).json()
    item = client.put(
        f"/api/v1/cases/{item['id']}/subjects",
        json={"revision": item["revision"], "links": [{"subject_id": owner["id"], "role": "applicant"}]},
    ).json()
    notice = f"合成场景验证，非官方规则。需提供{material}，并填写{field}。"
    source = text_document(client, item, notice, "source", "接收要求")
    item = current(client, item)
    rule = {
        "id": "scenario-field",
        "title": f"{material}的{field}",
        "kind": "required_field",
        "document_type": material,
        "parameters": {"field": field},
        "source_evidence": [{"document_id": source["id"], "page": 1, "quote": notice}],
    }
    draft = client.post(
        f"/api/v1/cases/{item['id']}/rule-sets", json={"revision": item["revision"], "requirements": [rule]}
    ).json()
    assert (
        client.post(
            f"/api/v1/rule-sets/{draft['id']}/activate", json={"revision": item["revision"]}
        ).status_code
        == 200
    )
    item = check(client, item)
    path = f"/api/v1/cases/{item['id']}/issues"
    assert client.get(path).json()["items"][0]["status"] == "open"
    upload = client.post(
        "/api/v1/assets", files={"file": (material + ".txt", f"{material}\n{field}：{value}".encode())}
    )
    assert upload.status_code == 201, upload.text
    assert (
        client.post(
            f"/api/v1/cases/{item['id']}/document-links",
            json={
                "revision": item["revision"],
                "asset_revision_id": upload.json()["asset"]["latest"]["id"],
                "category": material,
            },
        ).status_code
        == 201
    )
    task = claim()
    assert task[2] == "parse"
    process(*task)
    item = check(client, item)
    assert item["checklist"]["status"] == "ready"
    assert client.get(path).json()["items"][0]["status"] == "resolved"


def test_background_check_syncs_issues_without_model_in_test(client, monkeypatch):
    from app import worker

    monkeypatch.setattr(worker, "run_agent", lambda *args: None)
    item = activate_rule(client, case(client))
    response = client.post(f"/api/v1/cases/{item['id']}/checks", json={"revision": item["revision"]})
    assert response.status_code == 202
    task = claim()
    assert task[2] == "check"
    process(*task)
    result = client.get(f"/api/v1/cases/{item['id']}/issues").json()
    assert result["can_sync"] and result["items"][0]["status"] == "open"


def test_manual_attestation_resolves_without_changing_machine_verdict(client):
    item = case(client)
    text_document(client, item, "申请表\n姓名：合成")
    item = check(client, activate_rule(client, item, kind="manual_review"))
    path = f"/api/v1/cases/{item['id']}/issues"
    response = client.post(
        f"/api/v1/cases/{item['id']}/attestations",
        json={"revision": item["revision"], "requirement_id": "name", "note": "已查看合成原件"},
    )
    assert response.status_code == 200
    issue = client.get(path).json()["items"][0]
    assert issue["status"] == "resolved" and issue["verdict"] == "unknown"
    assert "本人已确认" in issue["reason"] and issue["next_action"] == ""
    first_revision = issue["revision"]
    client.post(path + "/sync", json={"revision": item["revision"]})
    assert client.get(path).json()["items"][0]["revision"] == first_revision


def test_scenario_cannot_be_replaced_by_case_metadata_edit(client):
    item = case(client, scenario_id="job_application")
    payload = {"title": item["title"], "revision": item["revision"]}
    assert (
        client.patch(
            f"/api/v1/cases/{item['id']}", json={**payload, "scenario_id": "business_entry"}
        ).status_code
        == 422
    )
    assert (
        client.patch(f"/api/v1/cases/{item['id']}", json={**payload, "kind": "business_entry"}).status_code
        == 422
    )
    response = client.patch(f"/api/v1/cases/{item['id']}", json=payload)
    assert response.status_code == 200
    assert response.json()["scenario"]["id"] == "job_application"
    assert response.json()["kind"] == "job_application"
