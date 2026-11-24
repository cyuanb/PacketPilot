import uuid

import pytest
from app import agent, main, worker
from app import db as db_module
from app.config import settings
from app.db import Base
from app.models import User
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def database(monkeypatch, tmp_path):
    """Each integration test owns a uniquely named PostgreSQL schema, never application tables."""
    schema = "pp_test_" + uuid.uuid4().hex
    admin = create_engine(settings.database_url, hide_parameters=True)
    with admin.begin() as conn:
        conn.execute(text('CREATE SCHEMA "' + schema + '"'))
    engine = create_engine(
        settings.database_url, hide_parameters=True, connect_args={"options": "-csearch_path=" + schema}
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    for module in (db_module, main, agent, worker):
        monkeypatch.setattr(module, "SessionLocal", factory)
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    main.login_attempts.clear()
    with factory.begin() as session:
        user = User(username="tester", password_hash=PasswordHasher().hash("test-password-123"))
        session.add(user)
    yield factory
    engine.dispose()
    assert schema.startswith("pp_test_") and len(schema) == 40
    with admin.begin() as conn:
        conn.execute(text('DROP SCHEMA "' + schema + '" CASCADE'))
    admin.dispose()


@pytest.fixture
def client(database):
    with TestClient(main.app, headers={"X-PacketPilot": "1"}) as c:
        r = c.post("/api/v1/auth/login", json={"username": "tester", "password": "test-password-123"})
        assert r.status_code == 200
        yield c
