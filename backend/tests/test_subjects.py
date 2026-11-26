from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from app.application.cases import expect_revision
from app.application.workspaces import personal_workspace
from app.models import Case, CaseSubjectRole, Membership, Run, SubjectProfile, User, Workspace
from argon2 import PasswordHasher
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError


def subject(client, name="林沐", kind="person", label="", **attributes):
    response = client.post(
        "/api/v1/subjects", json={"kind": kind, "name": name, "label": label, "attributes": attributes}
    )
    assert response.status_code == 201, response.text
    return response.json()


def update_body(s, **changes):
    return {**{k: s[k] for k in ("kind", "name", "label", "attributes", "revision", "archived")}, **changes}


def test_workspace_provision_is_idempotent_and_rename_has_revision(client):
    first = client.get("/api/v1/workspace").json()
    assert client.get("/api/v1/workspace").json() == first
    renamed = client.patch("/api/v1/workspace", json={"name": "材料准备空间", "revision": first["revision"]})
    assert renamed.status_code == 200 and renamed.json()["revision"] == first["revision"] + 1
    assert (
        client.patch("/api/v1/workspace", json={"name": "旧页面", "revision": first["revision"]}).status_code
        == 409
    )


def test_concurrent_workspace_provision_creates_one_membership(database):
    with database() as db:
        user_id = db.scalar(select(User.id))

    def provision(_):
        with database.begin() as db:
            return personal_workspace(db, user_id).id

    with ThreadPoolExecutor(max_workers=3) as pool:
        ids = list(pool.map(provision, range(3)))
    assert len(set(ids)) == 1
    with database() as db:
        assert db.scalar(select(func.count()).select_from(Membership)) == 1


def test_concurrent_workspace_edit_refreshes_preloaded_revision(client, database):
    workspace = client.get("/api/v1/workspace").json()
    gate = Barrier(2)

    def rename(name):
        try:
            with database.begin() as db:
                preloaded = db.get(Workspace, workspace["id"])
                gate.wait(timeout=5)
                locked = personal_workspace(db, preloaded.owner_id, True)
                expect_revision(locked, workspace["revision"])
                locked.name = name
                locked.revision += 1
            return 200
        except HTTPException as error:
            return error.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(rename, ["First", "Second"])) == [200, 409]


def test_same_name_profiles_and_organization_representative_are_distinct(client):
    a = subject(client, label="申请人")
    b = subject(client, label="推荐人")
    org = subject(client, kind="organization", registration_number="synthetic-registration")
    assert len({a["id"], b["id"], org["id"]}) == 3
    c = client.post("/api/v1/cases", json={"title": "组织入驻"}).json()
    links = [
        {"subject_id": org["id"], "role": "applicant"},
        {"subject_id": a["id"], "role": "representative"},
        {"subject_id": b["id"], "role": "recommender"},
    ]
    response = client.put(
        f"/api/v1/cases/{c['id']}/subjects", json={"revision": c["revision"], "links": links}
    )
    assert response.status_code == 200, response.text
    saved = response.json()
    assert saved["revision"] == c["revision"] + 1
    assert saved["facts"] == {}  # Profile attributes never silently become confirmed case facts.
    assert {(s["subject_id"], s["role"]) for s in saved["subjects"]} == {
        (s["subject_id"], s["role"]) for s in links
    }
    assert len(client.get(f"/api/v1/subjects/{a['id']}").json()["cases"]) == 1
    assert (
        client.put(
            f"/api/v1/cases/{c['id']}/subjects", json={"revision": c["revision"], "links": []}
        ).status_code
        == 409
    )


@pytest.mark.parametrize(
    "kind,role",
    [("organization", "recommender"), ("organization", "representative"), ("person", "organization")],
)
def test_role_type_mismatch_rejected(client, kind, role):
    s = subject(client, kind=kind)
    c = client.post("/api/v1/cases", json={"title": "类型核对"}).json()
    r = client.put(
        f"/api/v1/cases/{c['id']}/subjects",
        json={"revision": c["revision"], "links": [{"subject_id": s["id"], "role": role}]},
    )
    assert r.status_code == 422
    assert client.get(f"/api/v1/cases/{c['id']}").json()["subjects"] == []


def test_profile_edit_stales_linked_cases_and_preserves_job_snapshot(client, database):
    s = subject(client, email="synthetic@example.invalid")
    c = client.post("/api/v1/demo").json()
    c = client.put(
        f"/api/v1/cases/{c['id']}/subjects",
        json={"revision": c["revision"], "links": [{"subject_id": s["id"], "role": "applicant"}]},
    ).json()
    assert c["checklist"]["stale"] is True
    run = client.post(f"/api/v1/cases/{c['id']}/checks", json={"revision": c["revision"]}).json()
    r = client.patch(f"/api/v1/subjects/{s['id']}", json=update_body(s, name="林沐（确认姓名）"))
    assert r.status_code == 200
    changed = client.get(f"/api/v1/cases/{c['id']}").json()
    assert changed["revision"] == c["revision"] + 1
    assert changed["subjects"][0]["name"] == "林沐（确认姓名）"
    with database() as db:
        snapshot = db.get(Run, run["id"]).snapshot
        assert snapshot["subjects"][0]["name"] == "林沐"
        assert "attributes" not in snapshot["subjects"][0]
    assert client.patch(f"/api/v1/subjects/{s['id']}", json=update_body(s, name="旧写入")).status_code == 409


def test_archived_profiles_preserve_links_but_cannot_gain_new_roles(client):
    s = subject(client)
    c = client.post("/api/v1/cases", json={"title": "档案归档"}).json()
    links = [{"subject_id": s["id"], "role": "applicant"}]
    client.put(f"/api/v1/cases/{c['id']}/subjects", json={"revision": c["revision"], "links": links})
    s = client.patch(f"/api/v1/subjects/{s['id']}", json=update_body(s, archived=True)).json()
    assert client.get("/api/v1/subjects").json()["total"] == 0
    assert client.get("/api/v1/subjects?include_archived=true").json()["total"] == 1
    c = client.get(f"/api/v1/cases/{c['id']}").json()
    assert c["subjects"][0]["archived"] is True
    assert (
        client.put(
            f"/api/v1/cases/{c['id']}/subjects",
            json={"revision": c["revision"], "links": links + [{"subject_id": s["id"], "role": "contact"}]},
        ).status_code
        == 409
    )
    assert (
        client.put(
            f"/api/v1/cases/{c['id']}/subjects", json={"revision": c["revision"], "links": []}
        ).status_code
        == 200
    )
    assert client.patch(f"/api/v1/subjects/{s['id']}", json=update_body(s, archived=False)).status_code == 200


def test_foreign_workspace_resources_and_database_constraints(client, database):
    own = subject(client)
    c = client.post("/api/v1/cases", json={"title": "我的事项"}).json()
    with database.begin() as db:
        other = User(username="other", password_hash=PasswordHasher().hash("other-password"))
        db.add(other)
        db.flush()
        space = personal_workspace(db, other.id)
        foreign = SubjectProfile(workspace_id=space.id, kind="person", name="外部主体")
        db.add(foreign)
        db.flush()
        foreign_id, space_id = foreign.id, space.id
    assert client.get(f"/api/v1/subjects/{foreign_id}").status_code == 404
    assert client.patch(f"/api/v1/subjects/{foreign_id}", json=update_body(own)).status_code == 404
    assert (
        client.put(
            f"/api/v1/cases/{c['id']}/subjects",
            json={"revision": c["revision"], "links": [{"subject_id": foreign_id, "role": "applicant"}]},
        ).status_code
        == 404
    )
    assert client.get("/api/v1/subjects").json()["total"] == 1
    with pytest.raises(IntegrityError), database.begin() as db:
        db.add(
            CaseSubjectRole(
                case_id=c["id"], workspace_id=c["workspace_id"], subject_id=foreign_id, role="applicant"
            )
        )
    with pytest.raises(IntegrityError), database.begin() as db:
        db.get(Case, c["id"]).workspace_id = space_id
    client.post("/api/v1/auth/logout")
    client.post("/api/v1/auth/login", json={"username": "other", "password": "other-password"})
    assert (
        client.put(
            f"/api/v1/cases/{c['id']}/subjects", json={"revision": c["revision"], "links": []}
        ).status_code
        == 404
    )
    assert client.get(f"/api/v1/subjects/{own['id']}").status_code == 404


def test_missing_membership_does_not_self_repair(client, database):
    s = subject(client)
    c = client.post("/api/v1/cases", json={"title": "受控事项"}).json()
    with database.begin() as db:
        membership = db.scalar(select(Membership))
        db.delete(membership)
    assert client.get("/api/v1/workspace").status_code == 403
    assert client.get(f"/api/v1/subjects/{s['id']}").status_code == 403
    assert client.get(f"/api/v1/cases/{c['id']}").status_code == 404
    assert client.get("/api/v1/cases").json() == []


@pytest.mark.parametrize(
    "body",
    [
        {"kind": "person", "name": "  "},
        {"kind": "company", "name": "示例"},
        {"kind": "person", "name": "示例", "attributes": {"registration_number": "x"}},
        {"kind": "organization", "name": "示例", "attributes": {"email": "x"}},
        {"kind": "person", "name": "示例", "workspace_id": "foreign"},
    ],
)
def test_profile_input_is_typed_and_cannot_override_ownership(client, body):
    assert client.post("/api/v1/subjects", json=body).status_code == 422


def test_search_pagination_duplicates_and_case_delete(client):
    s = subject(client, name="同名", label="导师 100%")
    subject(client, name="同名", label="申请人")
    assert client.get("/api/v1/subjects?q=%25").json()["total"] == 1
    assert len(client.get("/api/v1/subjects?limit=1&offset=1").json()["items"]) == 1
    c = client.post("/api/v1/cases", json={"title": "删除关联"}).json()
    link = {"subject_id": s["id"], "role": "applicant"}
    assert (
        client.put(
            f"/api/v1/cases/{c['id']}/subjects", json={"revision": c["revision"], "links": [link, link]}
        ).status_code
        == 422
    )
    assert (
        client.put(
            f"/api/v1/cases/{c['id']}/subjects", json={"revision": c["revision"], "links": [link]}
        ).status_code
        == 200
    )
    assert client.delete(f"/api/v1/cases/{c['id']}").status_code == 200
    assert client.get(f"/api/v1/subjects/{s['id']}").json()["cases"] == []
