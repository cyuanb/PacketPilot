import hashlib
import json

import pytest
from alembic import command
from sqlalchemy import inspect, text
from sqlalchemy.exc import DBAPIError
from test_workspace_migration import migration_database as migration_database


def seed(config, connection):
    command.upgrade(config, "0002")
    connection.execute(text("INSERT INTO users VALUES ('owner','owner','synthetic')"))
    connection.execute(
        text("INSERT INTO workspaces VALUES ('space','owner','Space',1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)")
    )
    connection.execute(text("INSERT INTO memberships VALUES ('space','owner','owner')"))
    connection.execute(
        text("""INSERT INTO cases (id,owner_id,workspace_id,title,institution,kind,deadline,timezone,archived,revision,facts,created_at,updated_at)
        VALUES ('case','owner','space','Synthetic','','other','','Asia/Shanghai',false,3,'{}',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)""")
    )


def document(connection, identifier, logical, version, body, digest, size, key="", method="pasted"):
    connection.execute(
        text("""INSERT INTO document_versions (id,case_id,logical_id,version,active,title,purpose,category,filename,storage_key,sha256,mime,size,parse_status,pages,parse_note,parse_method,created_at)
        VALUES (:id,'case',:logical,:version,true,'Synthetic','material','','synthetic.txt',:key,:digest,'text/plain',:size,'ready',CAST(:pages AS jsonb),'',:method,CURRENT_TIMESTAMP)"""),
        {
            "id": identifier,
            "logical": logical,
            "version": version,
            "key": key,
            "digest": digest,
            "size": size,
            "method": method,
            "pages": json.dumps([{"number": 1, "label": "全文", "text": body}], ensure_ascii=False),
        },
    )


def test_backfill_preserves_hashes_original_text_corrections_and_case_rows(migration_database):
    config, connection = migration_database
    seed(config, connection)
    original = "原始通知\n".encode()
    digest = hashlib.sha256(original).hexdigest()
    document(connection, "doc1", "text-logical", 1, original.decode(), digest, len(original))
    document(
        connection, "doc2", "text-logical", 2, "校订内容", digest, len(original), method="user_corrected"
    )
    document(
        connection,
        "doc3",
        "file-logical",
        1,
        "提取内容",
        "recorded-file-hash",
        100,
        key="original.txt",
        method="native",
    )
    before = (
        connection.execute(text("SELECT to_jsonb(d) FROM document_versions d ORDER BY id")).scalars().all()
    )
    case_before = connection.scalar(text("SELECT to_jsonb(c) FROM cases c"))
    connection.commit()
    command.upgrade(config, "0003")
    assert (
        connection.execute(
            text("SELECT to_jsonb(d) - 'asset_revision_id' FROM document_versions d ORDER BY id")
        )
        .scalars()
        .all()
        == before
    )
    assert connection.scalar(text("SELECT to_jsonb(c) FROM cases c")) == case_before
    assert connection.scalar(text("SELECT count(*) FROM assets")) == 2
    assert connection.scalar(text("SELECT count(*) FROM asset_revisions")) == 3
    assert connection.scalar(text("SELECT count(*) FROM blobs")) == 2
    assert connection.scalar(text("SELECT inline_content FROM blobs WHERE storage_key IS NULL")) == original
    assert (
        connection.scalar(text("SELECT text_snapshot FROM asset_revisions WHERE id='doc2'"))[0]["text"]
        == "校订内容"
    )
    assert connection.scalar(text("SELECT count(*) FROM document_versions WHERE asset_revision_id=id")) == 3
    for table, update in (
        ("asset_revisions", "filename='overwritten.txt'"),
        ("blobs", "sha256='overwritten'"),
    ):
        with pytest.raises(DBAPIError, match="immutable"), connection.begin_nested():
            connection.execute(text(f"UPDATE {table} SET {update}"))
    connection.commit()
    with pytest.raises(RuntimeError, match="Library data exists"):
        command.downgrade(config, "0002")
    connection.rollback()
    assert connection.scalar(text("SELECT count(*) FROM asset_revisions")) == 3


def test_unrecoverable_inline_original_is_not_fabricated(migration_database):
    config, connection = migration_database
    seed(config, connection)
    document(
        connection,
        "corrected-only",
        "missing-original",
        2,
        "校订内容",
        "unknown-original-hash",
        200,
        method="user_corrected",
    )
    connection.commit()
    command.upgrade(config, "0003")
    assert connection.scalar(text("SELECT inline_content FROM blobs")) is None
    assert connection.scalar(text("SELECT sha256 FROM blobs")) == "unknown-original-hash"
    assert connection.scalar(text("SELECT text_snapshot FROM asset_revisions"))[0]["text"] == "校订内容"


def test_conflicting_shared_original_metadata_aborts_backfill(migration_database):
    config, connection = migration_database
    seed(config, connection)
    document(connection, "a", "logical", 1, "old", "first-hash", 3, key="same.txt")
    document(connection, "b", "logical", 2, "new", "different-hash", 3, key="same.txt")
    connection.commit()
    with pytest.raises(RuntimeError, match="Conflicting legacy metadata"):
        command.upgrade(config, "0003")
    connection.rollback()
    assert "asset_revision_id" not in {
        column["name"] for column in inspect(connection).get_columns("document_versions")
    }
    assert connection.scalar(text("SELECT count(*) FROM document_versions")) == 2


def test_empty_install_can_round_trip_library_migration(migration_database):
    config, connection = migration_database
    command.upgrade(config, "0003")
    command.downgrade(config, "0002")
    assert not inspect(connection).has_table("assets")
    connection.commit()
    command.upgrade(config, "0003")
    assert inspect(connection).has_table("assets")
