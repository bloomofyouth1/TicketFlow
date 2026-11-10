from types import SimpleNamespace

from app.agents import resolution_agent as agent


def fake_response(text="", calls=None):
    calls = calls or []
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                finish_reason=(
                    "tool_calls" if calls else "stop"
                ),
                message=SimpleNamespace(
                    content=text,
                    tool_calls=calls,
                ),
            )
        ],
        usage=SimpleNamespace(
            prompt_tokens=100,
            completion_tokens=30,
        ),
    )


def fake_tool_call():
    payload = {
        "id": "call_001",
        "type": "function",
        "function": {
            "name": "search_faq",
            "arguments": '{"query":"忘记密码怎么重置"}',
        },
    }

    return SimpleNamespace(
        id="call_001",
        function=SimpleNamespace(
            name="search_faq",
            arguments=payload["function"]["arguments"],
        ),
        model_dump=lambda: payload,
    )


def test_agent_tool_calling(monkeypatch):
    responses = iter([
        fake_response(calls=[fake_tool_call()]),
        fake_response("根据FAQ-001可以重置密码"),
    ])

    monkeypatch.setattr(
        agent,
        "request_model",
        lambda messages: next(responses),
    )

    result = agent.run_resolution_agent(
        "忘记密码，怎么重置密码？"
    )

    assert result.method == "agent_guarded"
    assert result.action == "suggest_reply"
    assert result.faq_id == "FAQ-001"


def test_agent_without_evidence_escalates(monkeypatch):
    monkeypatch.setattr(
        agent,
        "request_model",
        lambda messages: fake_response("直接修改密码即可"),
    )

    result = agent.run_resolution_agent(
        "忘记密码，怎么重置密码？"
    )

    assert result.action == "escalate"
    assert result.suggested_reply is None


def test_agent_model_failure_escalates(monkeypatch):
    def fail(messages):
        raise TimeoutError("mock timeout")

    monkeypatch.setattr(agent, "request_model", fail)

    result = agent.run_resolution_agent(
        "忘记密码，怎么重置密码？"
    )

    assert result.action == "escalate"
    assert result.method == "agent_guarded"


def test_high_risk_ticket_escalates(monkeypatch):
    responses = iter([
        fake_response(calls=[fake_tool_call()]),
        fake_response("建议检查服务器配置"),
    ])
    monkeypatch.setattr(
        agent,
        "request_model",
        lambda messages: next(responses),
    )

    result = agent.run_resolution_agent(
        "企业后台提示HTTP 500"
    )

    assert result.action == "escalate"
    assert result.suggested_reply is None


def test_agent_tool_budget(monkeypatch):
    def too_many_calls(messages):
        calls = [fake_tool_call() for _ in range(3)]
        return fake_response(calls=calls)

    monkeypatch.setattr(
        agent, "request_model", too_many_calls
    )

    result = agent.run_resolution_agent(
        "忘记密码，怎么重置密码？"
    )

    assert result.action == "escalate"
