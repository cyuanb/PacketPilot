import hashlib

import pytest
from alembic import command
from sqlalchemy import text
from test_asset_migration import document, seed
from test_workspace_migration import migration_database as migration_database


def test_workflow_backfill_pins_every_legacy_version_without_changing_rows(migration_database):
    config, connection = migration_database
    seed(config, connection)
    raw = "申请表\n姓名：合成".encode()
    document(connection, "old-doc", "old-logical", 1, raw.decode(), hashlib.sha256(raw).hexdigest(), len(raw))
    connection.commit()
    command.upgrade(config, "0003")
    tables = ("cases", "document_versions", "assets", "asset_revisions", "blobs")
    before = {
        name: connection.execute(text(f"SELECT to_jsonb(t) FROM {name} t ORDER BY id")).scalars().all()
        for name in tables
    }
    connection.commit()
    command.upgrade(config, "0004")
    for name in tables:
        after = (
            connection.execute(text(f"SELECT to_jsonb(t) - 'scenario_snapshot' FROM {name} t ORDER BY id"))
            .scalars()
            .all()
        )
        assert after == before[name]
    row = connection.execute(
        text("SELECT document_id, asset_revision_id, case_id, workspace_id FROM case_document_links")
    ).one()
    assert tuple(row) == ("old-doc", "old-doc", "case", "space")
    assert connection.scalar(text("SELECT count(*) FROM issues")) == 0
    connection.commit()
    command.downgrade(config, "0003")
    assert (
        connection.execute(text("SELECT to_jsonb(t) FROM cases t ORDER BY id")).scalars().all()
        == before["cases"]
    )


def test_workflow_downgrade_protects_scenario_data(migration_database):
    config, connection = migration_database
    seed(config, connection)
    connection.commit()
    command.upgrade(config, "0004")
    connection.execute(
        text("UPDATE cases SET scenario_snapshot=jsonb_build_object('id','synthetic-scenario')")
    )
    connection.commit()
    with pytest.raises(RuntimeError, match="Workflow data exists"):
        command.downgrade(config, "0003")
    connection.rollback()
    assert connection.scalar(text("SELECT scenario_snapshot->>'id' FROM cases")) == "synthetic-scenario"
