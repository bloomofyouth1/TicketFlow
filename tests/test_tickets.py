import pytest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base, get_db
from app.main import app


@pytest.fixture
def client(tmp_path):
    # 每次测试使用独立的临时数据库
    db_path = tmp_path / "test.db"

    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )

    TestingSession = sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )

    Base.metadata.create_all(bind=engine)

    def override_get_db():
        with TestingSession() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_health(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_create_and_get_ticket(client):
    payload = {
        "user_id": "customer_test",
        "content": "系统登录失败，错误代码500",
    }

    response = client.post("/tickets", json=payload)

    assert response.status_code == 201

    data = response.json()

    assert data["user_id"] == "customer_test"
    assert data["status"] == "pending"
    assert "id" in data

    ticket_id = data["id"]

    get_response = client.get(f"/tickets/{ticket_id}")

    assert get_response.status_code == 200
    assert get_response.json()["id"] == ticket_id


def test_empty_content_rejected(client):
    response = client.post(
        "/tickets",
        json={
            "user_id": "customer_test",
            "content": "",
        },
    )

    assert response.status_code == 422


def test_missing_ticket_returns_404(client):
    response = client.get(
        "/tickets/nonexistent-ticket-id"
    )

    assert response.status_code == 404
