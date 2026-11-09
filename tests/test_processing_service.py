def create_ticket(client, content):
    response = client.post(
        "/tickets",
        json={
            "user_id": "processing_test",
            "content": content,
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_password_ticket_processing(client):
    ticket_id = create_ticket(
        client,
        "忘记密码，怎么重置密码？",
    )

    response = client.post(
        f"/tickets/{ticket_id}/process"
    )

    assert response.status_code == 200

    result = response.json()
    assert result["action"] == "suggest_reply"
    assert result["faq_id"] == "FAQ-001"

    ticket = client.get(f"/tickets/{ticket_id}").json()
    assert ticket["status"] == "processing"

    events = client.get(
        f"/tickets/{ticket_id}/events"
    ).json()

    assert len(events) == 1
    assert events[0]["to_status"] == "processing"


def test_technical_issue_escalates(client):
    ticket_id = create_ticket(
        client,
        "系统提示 HTTP 500",
    )

    response = client.post(
        f"/tickets/{ticket_id}/process"
    )

    assert response.status_code == 200
    assert response.json()["action"] == "escalate"

    ticket = client.get(f"/tickets/{ticket_id}").json()
    assert ticket["status"] == "escalated"


def test_duplicate_processing_returns_existing(client):
    ticket_id = create_ticket(
        client,
        "忘记密码，怎么重置密码？",
    )

    first = client.post(
        f"/tickets/{ticket_id}/process"
    )
    second = client.post(
        f"/tickets/{ticket_id}/process"
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()

    events = client.get(
        f"/tickets/{ticket_id}/events"
    ).json()

    assert len(events) == 1


def test_process_missing_ticket(client):
    response = client.post(
        "/tickets/nonexistent-id/process"
    )
    assert response.status_code == 404


def test_processing_result_not_found(client):
    ticket_id = create_ticket(
        client,
        "测试未处理工单",
    )

    response = client.get(
        f"/tickets/{ticket_id}/processing-result"
    )

    assert response.status_code == 404
