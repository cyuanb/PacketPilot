import pytest
from app import agent
from app.agent_skills import SKILLS, load_skill, select_skill
from app.conversation import conversation_history
from app.models import Message, Run
from app.worker import claim
from test_workflow import case, current, text_document


@pytest.mark.parametrize(
    "kind,text,previous,expected",
    [
        ("extract", "", False, "requirement-extraction"),
        ("check", "", False, "application-preflight"),
        ("check", "", True, "amendment-recheck"),
        ("chat", "提取通知要求", False, "requirement-extraction"),
        ("chat", "解释这条依据", True, "evidence-explanation"),
        ("chat", "我现在还缺什么", False, "application-preflight"),
        ("chat", "补件后有哪些变化", True, "amendment-recheck"),
        ("chat", "我应该先做什么", False, "application-guidance"),
    ],
)
def test_skill_dispatch(kind, text, previous, expected):
    assert select_skill(kind, text, previous) == expected
    content, info = load_skill(expected)
    assert "name: " + expected in content and len(info["steps"]) >= 6
    assert len(info["hash"]) == 64 and len(SKILLS) == 5


def test_memory_uses_completed_turns_and_excludes_other_case_and_tool_fragments(client, database):
    a, b = case(client), case(client)
    with database.begin() as db:
        old = Run(
            case_id=a["id"],
            kind="chat",
            status="completed",
            revision=1,
            result={"answer": "我记住了星河项目，尚未确认背景。"},
        )
        other = Run(
            case_id=b["id"], kind="chat", status="completed", revision=1, result={"answer": "私有另一个事项"}
        )
        db.add_all([old, other])
        db.flush()
        db.add_all(
            [
                Message(case_id=a["id"], run_id=old.id, role="user", content="目标项目是星河"),
                Message(
                    case_id=a["id"],
                    run_id=old.id,
                    role="assistant",
                    content="不应进入对话的中间片段",
                    data={"tool_calls": [{}]},
                ),
                Message(case_id=b["id"], run_id=other.id, role="user", content="不应跨事项读取"),
            ]
        )
    with database() as db:
        history, info = conversation_history(db, a["id"], "new")
        assert history == [
            {"role": "user", "content": "目标项目是星河"},
            {"role": "assistant", "content": "我记住了星河项目，尚未确认背景。"},
        ]
        assert info["turns"] == 1
        assert conversation_history(db, a["id"], "new", budget=2)[0] == []


def test_chat_extraction_runs_actual_skill_and_persists_tools(client, database, monkeypatch):
    item = case(client)
    source = text_document(client, item, "申请表须填写姓名。", "source", "通知")
    item = current(client, item)
    response = client.post(
        f"/api/v1/cases/{item['id']}/messages", json={"revision": item["revision"], "text": "请提取通知要求"}
    )
    assert response.status_code == 202
    task = claim()
    seen = []
    rule = {
        "id": "name",
        "title": "填写姓名",
        "kind": "required_field",
        "document_type": "申请表",
        "parameters": {"field": "姓名"},
        "source_evidence": [{"document_id": source["id"], "page": 1, "quote": "申请表须填写姓名。"}],
    }
    import json

    def model(messages):
        seen.append(list(messages))
        n = len(seen)
        if n <= 2:
            return {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": f"call{n}",
                        "type": "function",
                        "function": {
                            "name": "get_case_context" if n == 1 else "save_requirement_draft",
                            "arguments": "{}" if n == 1 else json.dumps({"requirements": [rule]}),
                        },
                    }
                ],
            }, {}
        return {"role": "assistant", "content": "阅读范围：通知。要求草稿已保存。下一步请审阅并启用。"}, {}

    monkeypatch.setattr(agent, "model_request", model)
    agent.run_agent(task[0], task[1])
    with database() as db:
        run = db.get(Run, task[0])
        assert run.result["draft_id"]
        assert run.result["skill"]["name"] == "requirement-extraction"
        assert [s["status"] for s in run.result["tool_steps"]] == ["completed", "completed"]
        assert "通知要求提取" in seen[0][0]["content"]
        assert seen[1][-1]["role"] == "tool" and seen[2][-1]["tool_call_id"] == "call2"
    assert not current(client, item)["checklist"]["requirements"]


def test_recall_is_scoped_and_returns_original_statements(client, database):
    a, b = case(client), case(client)
    with database.begin() as db:
        for c, content in [(a, "之前提到项目星河"), (b, "别的事项星河秘密")]:
            old = Run(case_id=c["id"], kind="chat", status="completed", revision=1)
            db.add(old)
            db.flush()
            db.add(Message(case_id=c["id"], run_id=old.id, role="user", content=content))
    response = client.post(
        f"/api/v1/cases/{a['id']}/messages", json={"revision": a["revision"], "text": "我之前说的星河是什么"}
    )
    assert response.is_success
    task = claim()
    result = agent.execute_tool(task[0], task[1], "recall_conversation", {"query": "星河"})
    assert len(result["matches"]) == 1 and result["matches"][0]["text"] == "之前提到项目星河"


def test_official_tool_protocol_disables_hidden_reasoning(monkeypatch):
    import json

    import httpx
    from app.config import settings

    monkeypatch.setattr(settings, "llm_base_url", "https://api.deepseek.com")
    monkeypatch.setattr(settings, "llm_api_key", "synthetic-test-token")
    original = httpx.Client
    captured = []

    def handler(request):
        captured.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "合成回复",
                            "reasoning_content": "不得存储或展示的内容",
                        }
                    }
                ],
                "usage": {},
            },
        )

    monkeypatch.setattr(
        agent.httpx, "Client", lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs)
    )
    message, _ = agent.model_request([{"role": "user", "content": "合成请求"}])
    assert captured[0]["thinking"] == {"type": "disabled"}
    assert "reasoning_content" not in message
    assert any(t["function"]["name"] == "recall_conversation" for t in captured[0]["tools"])
