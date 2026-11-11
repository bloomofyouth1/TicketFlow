def test_legacy_status_api_disabled_by_default(
    client, monkeypatch
):
    monkeypatch.delenv(
        "TICKETFLOW_LEGACY_STATUS_WRITES",
        raising=False,
    )

    created = client.post(
        "/tickets",
        json={
            "user_id": "guard_test",
            "content": "无法登录企业后台",
        },
    )
    assert created.status_code == 201

    ticket_id = created.json()["id"]

    response = client.patch(
        f"/tickets/{ticket_id}/status",
        json={"status": "resolved"},
    )

    assert response.status_code == 403

    current = client.get(
        f"/tickets/{ticket_id}"
    )
    assert current.status_code == 200
    assert current.json()["status"] == "pending"


def test_review_api_still_available(client, monkeypatch):
    monkeypatch.setenv(
        "TICKETFLOW_ANALYZER", "rule"
    )
    monkeypatch.delenv(
        "TICKETFLOW_LEGACY_STATUS_WRITES",
        raising=False,
    )

    created = client.post(
        "/tickets",
        json={
            "user_id": "guard_test",
            "content": "忘记密码，怎么重置密码？",
        },
    )
    assert created.status_code == 201
    ticket_id = created.json()["id"]

    processed = client.post(
        f"/tickets/{ticket_id}/process"
    )
    assert processed.status_code == 200
    assert processed.json()["action"] == "suggest_reply"

    approved = client.post(
        f"/tickets/{ticket_id}/reviews/approve",
        json={
            "reviewer_id": "staff_001",
            "note": "人工确认通过",
        },
    )

    assert approved.status_code == 201

    ticket = client.get(
        f"/tickets/{ticket_id}"
    )
    assert ticket.json()["status"] == "resolved"
