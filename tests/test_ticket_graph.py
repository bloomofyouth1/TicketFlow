import pytest

from app.agents.ticket_graph import (
    run_ticket_graph,
    ticket_graph,
)
from app.services.ticket_processor import process_ticket_content


SAMPLES = [
    "忘记密码，怎么重置密码？",
    "系统提示 HTTP 500",
    "我想申请退款",
    "你们支持哪些报表功能？",
    "账号被冻结了",
    "如何申请企业发票",
]


@pytest.mark.parametrize("content", SAMPLES)
def test_graph_matches_rule_baseline(content):
    old = process_ticket_content(content)
    new = run_ticket_graph(content)

    assert new == old


def test_graph_suggest_reply_path():
    result = ticket_graph.invoke({
        "content": "忘记密码，怎么重置密码？",
        "execution_path": [],
    })

    assert result["action"] == "suggest_reply"
    assert result["faq_id"] == "FAQ-001"
    assert result["execution_path"] == [
        "classify",
        "retrieve",
        "decide",
        "suggest_reply",
    ]


def test_graph_escalation_path():
    result = ticket_graph.invoke({
        "content": "系统提示 HTTP 500",
        "execution_path": [],
    })

    assert result["action"] == "escalate"
    assert result["suggested_reply"] is None
    assert result["execution_path"][-1] == "escalate"
