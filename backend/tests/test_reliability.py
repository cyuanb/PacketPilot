from app.domain import check_one, condition_value
from app.models import Message, Run
from app.worker import claim
from sqlalchemy import func, select
from test_domain import doc, rule


def test_consistency_scopes_to_required_document_types():
    r = rule(
        "field_consistency",
        document_type="",
        parameters={"field": "姓名", "document_types": ["申请表", "成绩单"]},
    )
    f = check_one(
        r, [doc(), doc("申请表\n姓名：李沐", id="d2"), doc("推荐信\n推荐人姓名：张老师", id="d3")], {}
    )
    assert f["verdict"] == "pass"


def test_invalid_condition_is_unknown():
    assert condition_value("not a condition", {}) is None


def test_stale_inflight_run_cannot_become_current(client, monkeypatch):
    from app import worker

    c = client.post("/api/v1/demo").json()
    old_check = c["checklist"]["run_id"]
    client.post("/api/v1/cases/" + c["id"] + "/checks", json={"revision": c["revision"]})
    task = claim()
    client.post(
        "/api/v1/cases/" + c["id"] + "/facts/confirm",
        json={"revision": c["revision"], "facts": {"申请类别": "硕士"}},
    )
    monkeypatch.setattr(worker, "run_agent", lambda *_: None)
    worker.process(*task)
    current = client.get("/api/v1/cases/" + c["id"]).json()
    assert current["checklist"]["run_id"] == old_check
    assert current["checklist"]["stale"]
    assert client.get("/api/v1/runs/" + task[0]).json()["result"]["stale"]


def test_agent_loop_retains_tool_result_and_skill(client, database, monkeypatch):
    from app import agent

    c = client.post("/api/v1/demo").json()
    client.post("/api/v1/cases/" + c["id"] + "/checks", json={"revision": c["revision"]})
    task = claim()
    seen = []

    def model(messages):
        seen.append(messages.copy())
        if len(seen) == 1:
            return {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "run_checks", "arguments": "{}"},
                    }
                ],
            }, {}
        return {"role": "assistant", "content": "发现缺件，请补充材料。"}, {}

    monkeypatch.setattr(agent, "model_request", model)
    agent.run_agent(task[0], task[1])
    assert seen[1][-1]["role"] == "tool" and seen[1][-1]["tool_call_id"] == "call_1"
    assert "补件复检" in seen[0][0]["content"]
    with database() as db:
        r = db.get(Run, task[0])
        assert len(r.skill_hash) == 64
        assert (
            db.scalar(
                select(func.count())
                .select_from(Message)
                .where(Message.run_id == r.id, Message.role == "tool")
            )
            == 1
        )


def test_initial_migration_roundtrip(database):
    import importlib.util
    from pathlib import Path

    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from app.db import Base
    from sqlalchemy import inspect

    migration_path = Path(__file__).parents[1] / "migrations/versions/0001_initial.py"
    spec = importlib.util.spec_from_file_location("initial_migration", migration_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    engine = database.kw["bind"]
    # This engine points only to the isolated test schema from the fixture.
    Base.metadata.drop_all(engine)
    with engine.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            module.upgrade()
        assert "cases" in inspect(conn).get_table_names()
        with Operations.context(MigrationContext.configure(conn)):
            module.downgrade()
        assert "cases" not in inspect(conn).get_table_names()
