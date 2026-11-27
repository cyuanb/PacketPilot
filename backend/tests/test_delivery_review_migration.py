import hashlib

import pytest
from alembic import command
from sqlalchemy import text
from test_asset_migration import document, seed
from test_workspace_migration import migration_database as migration_database


def test_parse_migration_preserves_original_projection_and_backfills_history(migration_database):
    config, connection = migration_database
    seed(config, connection)
    raw = "申请表\n姓名：合成".encode()
    document(connection, "old-doc", "old-logical", 1, raw.decode(), hashlib.sha256(raw).hexdigest(), len(raw))
    connection.commit()
    command.upgrade(config, "0004")
    before = connection.execute(text("SELECT to_jsonb(d) FROM document_versions d")).scalar()
    connection.commit()
    command.upgrade(config, "0005")
    after = connection.execute(
        text("SELECT to_jsonb(d) - 'current_parse_id' - 'assignment' FROM document_versions d")
    ).scalar()
    assert after == before
    row = connection.execute(
        text(
            "SELECT p.pages, p.engine, p.version FROM parse_revisions p JOIN document_versions d ON d.current_parse_id=p.id"
        )
    ).one()
    assert row.pages == before["pages"] and row.engine == "legacy" and row.version == 1
    connection.execute(text("UPDATE parse_revisions SET version=2"))
    connection.commit()
    with pytest.raises(RuntimeError, match="Delivery/review data exists"):
        command.downgrade(config, "0004")
