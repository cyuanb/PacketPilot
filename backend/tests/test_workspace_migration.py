import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from app.config import settings
from sqlalchemy import create_engine, text


@pytest.fixture
def migration_database():
    schema = "pp_test_" + uuid.uuid4().hex
    admin = create_engine(settings.database_url, hide_parameters=True)
    with admin.begin() as connection:
        connection.execute(text('CREATE SCHEMA "' + schema + '"'))
    engine = create_engine(
        settings.database_url, hide_parameters=True, connect_args={"options": "-csearch_path=" + schema}
    )
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    config.set_main_option("script_location", str(Path(__file__).parents[1] / "migrations"))
    try:
        with engine.connect() as connection:
            config.attributes["connection"] = connection
            yield config, connection
    finally:
        engine.dispose()
        assert schema.startswith("pp_test_") and len(schema) == 40
        with admin.begin() as connection:
            connection.execute(text('DROP SCHEMA "' + schema + '" CASCADE'))
        admin.dispose()


def test_legacy_backfill_preserves_cases_documents_and_runs(migration_database):
    config, connection = migration_database
    command.upgrade(config, "0001")
    connection.execute(
        text("INSERT INTO users VALUES ('owner-a','owner-a','synthetic'), ('owner-b','owner-b','synthetic')")
    )
    connection.execute(
        text("""INSERT INTO cases (id, owner_id, title, institution, kind, deadline, timezone, archived, revision, facts, created_at, updated_at)
        VALUES ('case-a','owner-a','Same title','','exchange','','Asia/Shanghai',false,4,'{}',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),
               ('case-b','owner-b','Same title','','other','','Asia/Shanghai',true,9,'{}',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)""")
    )
    connection.execute(
        text("""INSERT INTO document_versions (id, case_id, logical_id, version, active, title, purpose, category, filename, storage_key, sha256, mime, size, parse_status, pages, parse_note, parse_method, created_at)
        VALUES ('doc-a','case-a','logical-a',2,true,'Synthetic','material','','synthetic.txt','synthetic-key','synthetic-hash','text/plain',10,'ready','[]','','native',CURRENT_TIMESTAMP)""")
    )
    connection.execute(
        text("""INSERT INTO runs (id,case_id,kind,status,revision,snapshot,payload,result,attempt,fence,cancel_requested,error,skill_hash,model,created_at,updated_at)
        VALUES ('run-a','case-a','check','completed',4,jsonb_build_object('legacy', true),'{}','{}',1,1,false,'','','',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)""")
    )
    connection.commit()
    before = {
        name: connection.execute(text(f"SELECT to_jsonb(t) FROM {name} t ORDER BY id")).scalars().all()
        for name in ("cases", "document_versions", "runs")
    }
    connection.commit()
    command.upgrade(config, "0002")
    spaces = connection.execute(text("SELECT id, owner_id FROM workspaces ORDER BY owner_id")).all()
    assert len(spaces) == 2 and spaces[0].id != spaces[1].id
    assert connection.scalar(text("SELECT count(*) FROM memberships")) == 2
    assert (
        connection.scalar(
            text(
                "SELECT count(*) FROM cases c JOIN workspaces w ON c.workspace_id=w.id AND c.owner_id=w.owner_id"
            )
        )
        == 2
    )
    for name in before:
        after = (
            connection.execute(text(f"SELECT to_jsonb(t) - 'workspace_id' FROM {name} t ORDER BY id"))
            .scalars()
            .all()
        )
        assert after == before[name]
    assert connection.scalar(text("SELECT count(*) FROM subject_profiles")) == 0
    connection.commit()
    # A safe rollback on an unused workspace restores the old shape; old migration is unchanged.
    command.downgrade(config, "0001")
    assert (
        connection.execute(text("SELECT to_jsonb(t) FROM cases t ORDER BY id")).scalars().all()
        == before["cases"]
    )
    connection.commit()
    command.upgrade(config, "0002")
    assert connection.scalar(text("SELECT count(*) FROM cases WHERE workspace_id IS NULL")) == 0


def test_new_install_and_rollback_refuse_to_drop_profiles(migration_database):
    config, connection = migration_database
    command.upgrade(config, "0002")
    connection.execute(text("INSERT INTO users VALUES ('owner','owner','synthetic')"))
    connection.execute(
        text("INSERT INTO workspaces VALUES ('space','owner','Space',1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)")
    )
    connection.execute(
        text(
            "INSERT INTO subject_profiles VALUES ('subject','space','person','Synthetic','','{}',false,1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
        )
    )
    connection.commit()
    with pytest.raises(RuntimeError, match="Workspace data exists"):
        command.downgrade(config, "0001")
    connection.rollback()
    assert connection.scalar(text("SELECT count(*) FROM subject_profiles")) == 1
