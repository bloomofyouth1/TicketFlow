import json

import pytest

from app.agents.resolution_agent import execute_tool


@pytest.fixture
def current_state():
    return {
        "content": "忘记密码，怎么重置密码？",
        "ticket_context": {
            "id": "ticket-001",
            "status": "pending",
            "content": "忘记密码，怎么重置密码？",
        },
        "history": [
            {
                "from_status": "pending",
                "to_status": "processing",
                "actor": "system",
            }
        ],
    }


def test_get_ticket(current_state):
    result = execute_tool(
        "get_ticket", "{}", current_state
    )
    assert result["id"] == "ticket-001"


def test_get_history(current_state):
    result = execute_tool(
        "get_history", "{}", current_state
    )
    assert len(result) == 1
    assert result[0]["actor"] == "system"


def test_cross_ticket_access_rejected(current_state):
    with pytest.raises(ValueError):
        execute_tool(
            "get_ticket",
            json.dumps({"ticket_id": "another-ticket"}),
            current_state,
        )


def test_unknown_tool_rejected(current_state):
    with pytest.raises(ValueError):
        execute_tool(
            "delete_ticket", "{}", current_state
        )


def test_invalid_faq_query_rejected(current_state):
    with pytest.raises(ValueError):
        execute_tool(
            "search_faq",
            '{"query": ""}',
            current_state,
        )
