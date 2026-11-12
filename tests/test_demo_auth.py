import pytest

@pytest.fixture
def protected_api(monkeypatch):
    monkeypatch.setenv(
        "TICKETFLOW_REQUIRE_AUTH", "1"
    )
    monkeypatch.setenv(
        "TICKETFLOW_ADMIN_TOKEN",
        "a" * 48,
    )
    yield
    monkeypatch.delenv(
        "TICKETFLOW_REQUIRE_AUTH",
        raising=False,
    )

def test_health_remains_public(client, protected_api):
    response = client.get("/health")
    assert response.status_code == 200

def test_ticket_list_requires_auth(
    client, protected_api
):
    response = client.get("/tickets")
    assert response.status_code == 401

def test_ticket_creation_requires_auth(
    client, protected_api
):
    response = client.post(
        "/tickets",
        json={
            "user_id": "unauthorized",
            "content": "test",
        },
    )
    assert response.status_code == 401

def test_invalid_token_is_rejected(
    client, protected_api
):
    response = client.get(
        "/auth/check",
        headers={
            "Authorization": "Bearer wrong-token"
        },
    )
    assert response.status_code == 401

def test_valid_token_is_accepted(
    client, protected_api
):
    response = client.get(
        "/auth/check",
        headers={
            "Authorization": "Bearer " + "a" * 48
        },
    )

    assert response.status_code == 200
    assert response.json()["authenticated"] is True

def test_missing_server_secret_fails_closed(
    client, protected_api, monkeypatch
):
    monkeypatch.delenv(
        "TICKETFLOW_ADMIN_TOKEN",
        raising=False,
    )

    response = client.get(
        "/tickets",
        headers={
            "Authorization": "Bearer " + "a" * 48
        },
    )
    assert response.status_code == 503
