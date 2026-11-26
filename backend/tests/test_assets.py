import hashlib

import pytest
from app.application.assets import original_path
from app.config import settings
from app.models import Asset, AssetRevision, Blob, Document, User
from argon2 import PasswordHasher
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


def upload(client, raw=b"original content", filename="sample.txt", asset=None):
    path = "/api/v1/assets" if asset is None else f"/api/v1/assets/{asset['id']}/versions"
    response = client.post(
        path, files={"file": (filename, raw)}, data={} if asset is None else {"revision": asset["revision"]}
    )
    assert response.status_code == 201, response.text
    return response.json()


def edit_body(asset, **changes):
    return {
        **{key: asset[key] for key in ("title", "category", "subject_id", "archived", "revision")},
        **changes,
    }


def test_upload_without_case_inbox_and_duplicate_versions_are_not_swallowed(client):
    first = upload(client)
    asset = first["asset"]
    assert asset["inbox"] is True and asset["latest"]["version"] == 1
    assert asset["usages"] == [] and first["duplicates"] == []
    assert client.get("/api/v1/cases").json() == []
    copy = upload(client)
    assert copy["asset"]["id"] != asset["id"]
    assert copy["duplicates"][0]["asset_id"] == asset["id"]
    next_result = upload(client, asset=asset)
    assert next_result["asset"]["latest"]["version"] == 2
    assert len(next_result["asset"]["versions"]) == 2 and next_result["duplicates"]
    assert client.get("/api/v1/assets?inbox=true").json()["total"] == 2


def test_old_bytes_and_metadata_remain_unchanged_after_append(client):
    first = upload(client, b"old bytes")["asset"]
    old = first["latest"]
    second = upload(client, b"new bytes", asset=first)["asset"]
    assert second["latest"]["sha256"] != old["sha256"]
    assert client.get(f"/api/v1/asset-revisions/{old['id']}/content").content == b"old bytes"
    assert client.get(f"/api/v1/asset-revisions/{second['latest']['id']}/content").content == b"new bytes"
    assert (
        client.get(f"/api/v1/asset-revisions/{old['id']}").json()["sha256"]
        == hashlib.sha256(b"old bytes").hexdigest()
    )
    assert (
        client.post(
            f"/api/v1/assets/{first['id']}/versions",
            data={"revision": first["revision"]},
            files={"file": ("stale.txt", b"wrong")},
        ).status_code
        == 409
    )
    assert len(client.get(f"/api/v1/assets/{first['id']}").json()["versions"]) == 2


def test_classification_subject_archival_and_search(client):
    subject = client.post("/api/v1/subjects", json={"kind": "organization", "name": "合成组织"}).json()
    a = upload(client)["asset"]
    a = client.patch(
        f"/api/v1/assets/{a['id']}",
        json=edit_body(a, subject_id=subject["id"], title="组织资质", category="资质"),
    ).json()
    assert not a["inbox"] and a["subject_name"] == "合成组织"
    assert client.get("/api/v1/assets?inbox=true").json()["total"] == 0
    assert client.get("/api/v1/assets?q=组织&category=资质&subject_id=" + subject["id"]).json()["total"] == 1
    archived = client.patch(f"/api/v1/assets/{a['id']}", json=edit_body(a, archived=True)).json()
    assert client.get("/api/v1/assets").json()["total"] == 0
    assert client.get("/api/v1/assets?include_archived=true").json()["total"] == 1
    assert (
        client.post(
            f"/api/v1/assets/{a['id']}/versions",
            data={"revision": archived["revision"]},
            files={"file": ("new.txt", b"data")},
        ).status_code
        == 409
    )
    assert (
        client.patch(f"/api/v1/assets/{a['id']}", json=edit_body(archived, archived=False)).status_code == 200
    )


def test_case_upload_and_removal_retain_library_original(client, database):
    case = client.post("/api/v1/cases", json={"title": "合成事项"}).json()
    response = client.post(
        f"/api/v1/cases/{case['id']}/documents", files={"file": ("proof.txt", b"original proof")}
    )
    assert response.status_code == 201
    document = response.json()["document"]
    library = client.get("/api/v1/assets").json()["items"][0]
    detail = client.get(f"/api/v1/assets/{library['id']}").json()
    assert detail["usages"][0]["document_id"] == document["id"]
    with database() as db:
        key = db.get(Document, document["id"]).storage_key
    assert client.delete(f"/api/v1/documents/{document['id']}").status_code == 200
    assert (settings.storage / key).is_file()
    assert client.get(f"/api/v1/assets/{library['id']}").json()["usages"] == []
    assert (
        client.get(f"/api/v1/asset-revisions/{detail['latest']['id']}/content").content == b"original proof"
    )


def test_library_append_does_not_change_case_and_case_replacement_appends_separately(client):
    case = client.post("/api/v1/demo").json()
    document = next(d for d in case["documents"] if d["purpose"] == "material")
    version = client.get("/api/v1/asset-revisions/" + document["asset_revision_id"]).json()
    asset = client.get("/api/v1/assets/" + version["asset_id"]).json()
    upload(client, b"library only", asset=asset)
    unchanged = client.get("/api/v1/cases/" + case["id"]).json()
    assert unchanged["revision"] == case["revision"]
    assert unchanged["checklist"]["stale"] is False
    corrected = client.post(
        "/api/v1/documents/" + document["id"] + "/correction",
        json={"revision": case["revision"], "text": "人工校订的申请表"},
    ).json()
    assert corrected["version"] == 2
    revised = client.get("/api/v1/assets/" + asset["id"]).json()
    assert [r["version"] for r in revised["versions"]] == [3, 2, 1]
    correction = client.get("/api/v1/asset-revisions/" + corrected["asset_revision_id"]).json()
    assert (
        correction["origin"] == "correction" and correction["text_snapshot"][0]["text"] == "人工校订的申请表"
    )
    original = client.get("/api/v1/documents/" + document["id"] + "/content").content
    assert client.get("/api/v1/asset-revisions/" + correction["id"] + "/content").content == original
    assert client.delete("/api/v1/cases/" + case["id"]).status_code == 200
    assert client.get("/api/v1/assets/" + asset["id"]).json()["usages"] == []
    assert client.get("/api/v1/asset-revisions/" + correction["id"] + "/content").content == original


def test_foreign_assets_bytes_and_duplicate_hints_are_isolated(client, database):
    own = upload(client)["asset"]
    with database.begin() as db:
        db.add(User(username="other", password_hash=PasswordHasher().hash("other-password")))
    client.post("/api/v1/auth/logout")
    client.post("/api/v1/auth/login", json={"username": "other", "password": "other-password"})
    other = upload(client)
    assert other["duplicates"] == []
    for path in (
        f"/assets/{own['id']}",
        f"/asset-revisions/{own['latest']['id']}",
        f"/asset-revisions/{own['latest']['id']}/content",
    ):
        assert client.get("/api/v1" + path).status_code == 404
    assert client.patch(f"/api/v1/assets/{own['id']}", json=edit_body(own)).status_code == 404
    assert (
        client.post(
            f"/api/v1/assets/{own['id']}/versions",
            data={"revision": own["revision"]},
            files={"file": ("new.txt", b"bad")},
        ).status_code
        == 404
    )
    foreign_subject = client.post("/api/v1/subjects", json={"kind": "person", "name": "其他账号"}).json()
    client.post("/api/v1/auth/logout")
    client.post("/api/v1/auth/login", json={"username": "tester", "password": "test-password-123"})
    assert (
        client.patch(
            f"/api/v1/assets/{own['id']}", json=edit_body(own, subject_id=foreign_subject["id"])
        ).status_code
        == 404
    )
    with pytest.raises(IntegrityError), database.begin() as db:
        db.get(Asset, own["id"]).subject_id = foreign_subject["id"]
    with pytest.raises(IntegrityError), database.begin() as db:
        db.get(AssetRevision, own["latest"]["id"]).blob_id = db.scalar(
            select(AssetRevision.blob_id).where(AssetRevision.id == other["asset"]["latest"]["id"])
        )


def test_bad_uploads_do_not_create_rows_or_files(client, database, monkeypatch):
    assert client.post("/api/v1/assets", files={"file": ("empty.txt", b"")}).status_code == 422
    assert client.post("/api/v1/assets", files={"file": ("script.html", b"html")}).status_code == 415
    monkeypatch.setattr(settings, "max_file_bytes", 4)
    assert client.post("/api/v1/assets", files={"file": ("large.txt", b"12345")}).status_code == 413
    with database() as db:
        assert db.scalar(select(Asset)) is None and db.scalar(select(Blob)) is None


def test_unavailable_original_and_optimistic_metadata_conflict(client, database):
    asset = upload(client)["asset"]
    assert (
        client.patch(f"/api/v1/assets/{asset['id']}", json=edit_body(asset, title="新名称")).status_code
        == 200
    )
    assert (
        client.patch(f"/api/v1/assets/{asset['id']}", json=edit_body(asset, title="旧写入")).status_code
        == 409
    )
    with database() as db:
        revision = db.get(AssetRevision, asset["latest"]["id"])
        blob = db.get(Blob, revision.blob_id)
        (settings.storage / blob.storage_key).unlink()
    response = client.get("/api/v1/asset-revisions/" + asset["latest"]["id"])
    assert response.json()["available"] is False
    assert client.get("/api/v1/asset-revisions/" + asset["latest"]["id"] + "/content").status_code == 404


def test_failed_commit_removes_staged_file(client, database, monkeypatch):
    def fail_commit(self):
        raise RuntimeError("synthetic commit failure")

    with monkeypatch.context() as patch:
        patch.setattr(Session, "commit", fail_commit)
        with pytest.raises(RuntimeError, match="synthetic commit failure"):
            client.post("/api/v1/assets", files={"file": ("staged.txt", b"not committed")})
    with database() as db:
        assert db.scalar(select(Asset)) is None and db.scalar(select(Blob)) is None
    assert list(settings.storage.glob("*.txt")) == []


@pytest.mark.parametrize(
    "key", ["../outside.txt", "..\\outside.txt", "C:\\outside.txt", "/outside.txt", ".", ".."]
)
def test_original_path_rejects_escape(key):
    assert original_path(key) is None


def test_case_upload_also_reports_exact_duplicates_without_merging(client):
    case = client.post("/api/v1/cases", json={"title": "重复文件核对"}).json()
    path = f"/api/v1/cases/{case['id']}/documents"
    first = client.post(path, files={"file": ("same.txt", b"same bytes")}).json()
    second = client.post(path, files={"file": ("same.txt", b"same bytes")}).json()
    assert first["duplicates"] == []
    assert second["duplicates"][0]["revision_id"] == first["document"]["asset_revision_id"]
    assert first["document"]["id"] != second["document"]["id"]
    assert len(client.get("/api/v1/cases/" + case["id"]).json()["documents"]) == 2


def test_lost_commit_acknowledgement_does_not_delete_committed_original(client, database, monkeypatch):
    original_commit = Session.commit

    def commit_then_fail(self):
        original_commit(self)
        raise RuntimeError("synthetic acknowledgement loss")

    with monkeypatch.context() as patch:
        patch.setattr(Session, "commit", commit_then_fail)
        with pytest.raises(RuntimeError, match="synthetic acknowledgement loss"):
            client.post("/api/v1/assets", files={"file": ("committed.txt", b"keep committed bytes")})
    with database() as db:
        blob = db.scalar(select(Blob))
        assert blob is not None
        assert (settings.storage / blob.storage_key).read_bytes() == b"keep committed bytes"
        assert db.scalar(select(AssetRevision)) is not None


def test_metadata_projection_does_not_load_original_bytes_or_text_snapshots(client, database):
    from app.application.assets import revision_query, revision_view
    from sqlalchemy import inspect

    client.post("/api/v1/demo")
    with database() as db:
        rows = db.execute(revision_query()).all()
        assert rows
        for revision, blob, has_text, has_inline in rows:
            assert "text_snapshot" in inspect(revision).unloaded
            assert "inline_content" in inspect(blob).unloaded
            result = revision_view(revision, blob, has_text=has_text, has_inline=has_inline)
            assert result["available"] and result["has_text_snapshot"]
            assert "text_snapshot" not in result
            assert "text_snapshot" in inspect(revision).unloaded
            assert "inline_content" in inspect(blob).unloaded
