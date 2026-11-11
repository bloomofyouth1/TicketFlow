import json

from app.models.agent_execution import AgentExecution
from app.main import app
from app.core.database import get_db


def create_ticket(client):
    response = client.post(
        "/tickets",
        json={
            "user_id": "metrics_test",
            "content": "忘记密码，怎么重置密码？",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_unprocessed_ticket_has_no_metrics(client):
    ticket_id = create_ticket(client)

    response = client.get(
        f"/tickets/{ticket_id}/agent-execution"
    )
    assert response.status_code == 404
    assert response.json()["detail"] == (
        "Agent execution not available"
    )


def test_agent_metrics_endpoint(client):
    db_session = next(app.dependency_overrides[get_db]())
    ticket_id = create_ticket(client)

    db_session.add(
        AgentExecution(
            ticket_id=ticket_id,
            model_calls=2,
            tool_calls=2,
            input_tokens=1100,
            output_tokens=200,
            latency_seconds=2.5,
            tool_names=json.dumps(
                ["search_faq", "get_ticket"]
            ),
            trace=json.dumps(
                ["model", "tools", "model", "finalize"]
            ),
            error_type=None,
            fallback=False,
        )
    )
    db_session.commit()

    response = client.get(
        f"/tickets/{ticket_id}/agent-execution"
    )

    assert response.status_code == 200

    data = response.json()
    assert data["total_tokens"] == 1300
    assert data["model_calls"] == 2
    assert data["tool_calls"] == 2
    assert data["tool_names"] == [
        "search_faq", "get_ticket"
    ]
    assert data["fallback"] is False


def test_missing_ticket_metrics(client):
    response = client.get(
        "/tickets/nonexistent/agent-execution"
    )
    assert response.status_code == 404
