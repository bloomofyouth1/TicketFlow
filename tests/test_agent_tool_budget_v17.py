import json
from types import SimpleNamespace

from app.agents import resolution_agent as agent


def test_remaining_slot_prioritizes_faq_and_answers_every_call():
    def tool_call(call_id, name, arguments):
        return SimpleNamespace(
            id=call_id,
            function=SimpleNamespace(name=name, arguments=arguments),
        )

    state = {
        "content": "我需要重设自己的登录密码，能提供官方的密码找回指引吗？",
        "messages": [],
        "evidence_ids": [],
        "tool_names": ["get_ticket", "get_history"],
        "tool_calls": agent.MAX_TOOL_CALLS - 1,
        "trace": [],
        "pending_calls": [
            tool_call("ticket", "get_ticket", "{}"),
            tool_call("faq", "search_faq", '{"query":"怎么操作？"}'),
        ],
    }

    result = agent.tools_node(state)
    replies = {
        message["tool_call_id"]: json.loads(message["content"])
        for message in result["messages"]
    }

    assert result["tool_calls"] == agent.MAX_TOOL_CALLS
    assert result["tool_names"][-1] == "search_faq"
    assert result["evidence_ids"] == ["FAQ-001"]
    assert replies["faq"][0]["id"] == "FAQ-001"
    assert replies["ticket"]["error"] == "ToolBudgetExceeded"
    assert "tool_skipped_budget:get_ticket" in result["trace"]


def test_last_model_round_has_no_tools(monkeypatch):
    def final_model(messages, *, allow_tools):
        assert allow_tools is False
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    finish_reason="stop",
                    message=SimpleNamespace(content="总结已有证据", tool_calls=[]),
                )
            ],
            usage=None,
        )

    monkeypatch.setattr(agent, "request_model", final_model)
    result = agent.model_node({
        "messages": [],
        "model_calls": agent.MAX_MODEL_CALLS - 1,
        "tool_calls": 1,
        "input_tokens": 100,
        "output_tokens": 20,
        "trace": [],
    })

    assert result["model_calls"] == agent.MAX_MODEL_CALLS
    assert result["final_answer"] == "总结已有证据"
    assert result["pending_calls"] == []
