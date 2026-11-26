"""HTTP compatibility checks for clients, streaming and app composition."""

import json
from pathlib import Path

import pytest
from app import main
from app.config import settings
from app.main import create_app
from app.models import RunEvent
from fastapi.testclient import TestClient
from sqlalchemy import select


def test_openapi_contract():
    expected = json.loads((Path(__file__).parent / "fixtures/api-contract.json").read_text(encoding="utf-8"))
    assert create_app().openapi() == expected


def test_factory_mounts_frontend_without_shadowing_api(monkeypatch, tmp_path, database):
    dist = tmp_path / "frontend" / "dist"
    dist.mkdir(parents=True)
    (dist / "index.html").write_text("<h1>PacketPilot test frontend</h1>", encoding="utf-8")
    monkeypatch.setattr(main, "ROOT", tmp_path)
    for app in (create_app(), create_app()):
        with TestClient(app) as browser:
            response = browser.get("/")
            assert response.status_code == 200
            assert response.text == "<h1>PacketPilot test frontend</h1>"
            assert response.headers["cache-control"] == "no-cache"
            assert browser.get("/api/v1/me").status_code == 401
            assert browser.get("/api/health").json() == {"status": "ok", "version": "0.2.0"}


def test_session_cookie_and_response_boundary(client):
    login = client.post("/api/v1/auth/login", json={"username": "tester", "password": "test-password-123"})
    assert login.status_code == 200
    cookie = login.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie and "path=/" in cookie
    assert "max-age=604800" in cookie
    assert ("; secure" in cookie) == settings.cookie_secure
    assert client.get("/api/v1/me").json() == {"username": "tester"}
    assert client.post("/api/v1/auth/logout").json() == {"ok": True}
    denied = client.get("/api/v1/me")
    assert denied.status_code == 401
    assert denied.json() == {"code": "http_401", "message": "请先登录"}
    assert denied.headers["cache-control"] == "no-store"
    assert denied.headers["x-content-type-options"] == "nosniff"
    assert len(denied.headers["x-request-id"]) == 16


@pytest.mark.parametrize("cursor_source", ["query", "header", "both"])
def test_sse_replays_after_cursor_across_batches(client, database, cursor_source):
    case = client.post("/api/v1/demo").json()
    run_id = case["runs"][0]["id"]
    with database.begin() as db:
        rows = [RunEvent(run_id=run_id, event="review.progress", data={"index": i}) for i in range(105)]
        db.add_all(rows)
        db.flush()
        ids = [r.id for r in rows]
    # Over 100 remaining events exercises both pagination and the terminal event.
    cursor = ids[2]
    params = {"after": cursor} if cursor_source == "query" else {"after": ids[0]}
    headers = {"Last-Event-ID": str(cursor)} if cursor_source != "query" else {}
    response = client.get(f"/api/v1/runs/{run_id}/events", params=params, headers=headers)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["x-accel-buffering"] == "no"
    assert response.headers["cache-control"] == "no-store"
    received = [int(line[4:]) for line in response.text.splitlines() if line.startswith("id: ")]
    with database() as db:
        expected = list(
            db.scalars(
                select(RunEvent.id)
                .where(RunEvent.run_id == run_id, RunEvent.id > cursor)
                .order_by(RunEvent.id)
            )
        )
    assert received == expected == ids[3:]
    assert response.text.count("event: done\n") == 1
    assert json.loads(response.text.split("event: review.progress\ndata: ")[1].split("\n")[0]) == {"index": 3}


def test_sse_invalid_cursor_uses_http_error_contract(client):
    case = client.post("/api/v1/demo").json()
    response = client.get(
        f"/api/v1/runs/{case['runs'][0]['id']}/events", headers={"Last-Event-ID": "invalid"}
    )
    assert response.status_code == 422
    assert response.json() == {"code": "http_422", "message": "无效事件游标"}
