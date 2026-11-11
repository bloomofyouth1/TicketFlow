import pytest


@pytest.fixture(autouse=True)
def use_rule_mode(monkeypatch):
    monkeypatch.setenv("TICKETFLOW_ANALYZER", "rule")


def create_and_process(client, content):
    response = client.post(
        "/tickets",
        json={
            "user_id": "review_test",
            "content": content,
        },
    )
    assert response.status_code == 201
    ticket_id = response.json()["id"]

    processed = client.post(
        f"/tickets/{ticket_id}/process"
    )
    assert processed.status_code == 200

    return ticket_id, processed.json()


def submit_review(client, ticket_id, decision):
    return client.post(
        f"/tickets/{ticket_id}/reviews/{decision}",
        json={
            "reviewer_id": "staff_001",
            "note": f"测试审核：{decision}",
        },
    )


def get_status(client, ticket_id):
    response = client.get(
        f"/tickets/{ticket_id}"
    )
    assert response.status_code == 200
    return response.json()["status"]


def test_approve_closes_ticket(client):
    ticket_id, result = create_and_process(
        client, "忘记密码，怎么重置密码？"
    )
    assert result["action"] == "suggest_reply"
    assert get_status(client, ticket_id) == "processing"

    review = submit_review(
        client, ticket_id, "approve"
    )

    assert review.status_code == 201
    assert review.json()["decision"] == "approve"
    assert get_status(client, ticket_id) == "resolved"

    events = client.get(
        f"/tickets/{ticket_id}/events"
    ).json()
    assert len(events) == 2
    assert events[-1]["to_status"] == "resolved"


def test_reject_then_human_resolve(client):
    ticket_id, _ = create_and_process(
        client, "忘记密码，怎么重置密码？"
    )

    rejected = submit_review(
        client, ticket_id, "reject"
    )
    assert rejected.status_code == 201
    assert get_status(client, ticket_id) == "escalated"

    resolved = submit_review(
        client, ticket_id, "resolve"
    )
    assert resolved.status_code == 201
    assert get_status(client, ticket_id) == "resolved"

    reviews = client.get(
        f"/tickets/{ticket_id}/reviews"
    )
    assert reviews.status_code == 200
    assert [
        item["decision"]
        for item in reviews.json()
    ] == ["reject", "resolve"]


def test_high_risk_requires_human_resolution(client):
    ticket_id, result = create_and_process(
        client, "企业后台提示 HTTP 500"
    )
    assert result["action"] == "escalate"

    approved = submit_review(
        client, ticket_id, "approve"
    )
    assert approved.status_code == 409

    resolved = submit_review(
        client, ticket_id, "resolve"
    )
    assert resolved.status_code == 201
    assert get_status(client, ticket_id) == "resolved"


def test_duplicate_review_rejected(client):
    ticket_id, _ = create_and_process(
        client, "忘记密码，怎么重置密码？"
    )

    first = submit_review(
        client, ticket_id, "approve"
    )
    second = submit_review(
        client, ticket_id, "approve"
    )

    assert first.status_code == 201
    assert second.status_code == 409

    reviews = client.get(
        f"/tickets/{ticket_id}/reviews"
    ).json()
    assert len(reviews) == 1


def test_invalid_review_state(client):
    response = client.post(
        "/tickets",
        json={
            "user_id": "review_test",
            "content": "未处理的测试工单",
        },
    )
    assert response.status_code == 201

    ticket_id = response.json()["id"]

    assert submit_review(
        client, ticket_id, "approve"
    ).status_code == 409

    assert submit_review(
        client, ticket_id, "resolve"
    ).status_code == 409


def test_missing_ticket_and_invalid_payload(client):
    response = client.get(
        "/tickets/nonexistent/reviews"
    )
    assert response.status_code == 404

    ticket_id, _ = create_and_process(
        client, "忘记密码，怎么重置密码？"
    )

    bad = client.post(
        f"/tickets/{ticket_id}/reviews/approve",
        json={
            "reviewer_id": "",
            "note": "",
        },
    )
    assert bad.status_code == 422
