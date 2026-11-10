from types import SimpleNamespace

from app.agents import hybrid_ticket_graph as hybrid
from app.llm.ticket_analyzer import TicketAnalysis


def fake_output(category, needs_human=False):
    return SimpleNamespace(
        analysis=TicketAnalysis(
            category=category,
            summary="测试摘要",
            priority="low",
            needs_human=needs_human,
        ),
        input_tokens=100,
        output_tokens=30,
        latency_seconds=0.2,
        model="mock-model",
    )


def test_hybrid_password(monkeypatch):
    monkeypatch.setattr(
        hybrid,
        "analyze_ticket",
        lambda content: fake_output("account"),
    )

    result = hybrid.run_hybrid_ticket_graph(
        "忘记密码，怎么重置密码？"
    )

    assert result.action == "suggest_reply"
    assert result.faq_id == "FAQ-001"
    assert result.method == "llm_guarded"


def test_hybrid_fallback(monkeypatch):
    def failure(content):
        raise TimeoutError("Simulated timeout")

    monkeypatch.setattr(
        hybrid,
        "analyze_ticket",
        failure,
    )

    result = hybrid.run_hybrid_ticket_graph(
        "忘记密码，怎么重置密码？"
    )

    assert result.action == "suggest_reply"
    assert result.method == "rule"


def test_hybrid_category_disagreement(monkeypatch):
    monkeypatch.setattr(
        hybrid,
        "analyze_ticket",
        lambda content: fake_output("billing"),
    )

    result = hybrid.run_hybrid_ticket_graph(
        "忘记密码，怎么重置密码？"
    )

    assert result.action == "escalate"
    assert result.suggested_reply is None


def test_hybrid_high_risk_guard(monkeypatch):
    monkeypatch.setattr(
        hybrid,
        "analyze_ticket",
        lambda content: fake_output(
            "technical_issue",
            needs_human=False,
        ),
    )

    result = hybrid.run_hybrid_ticket_graph(
        "企业后台提示 HTTP 500"
    )

    assert result.action == "escalate"
    assert result.suggested_reply is None


def test_hybrid_human_review(monkeypatch):
    monkeypatch.setattr(
        hybrid,
        "analyze_ticket",
        lambda content: fake_output(
            "account",
            needs_human=True,
        ),
    )

    result = hybrid.run_hybrid_ticket_graph(
        "忘记密码，怎么重置密码？"
    )

    assert result.action == "escalate"
