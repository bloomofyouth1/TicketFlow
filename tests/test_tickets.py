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


def test_valid_status_transition(client):
    response = client.post(
        "/tickets",
        json={
            "user_id": "test_user",
            "content": "测试状态更新",
        },
    )
    assert response.status_code == 201
    ticket_id = response.json()["id"]

    response = client.patch(
        f"/tickets/{ticket_id}/status",
        json={"status": "processing"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "processing"


def test_invalid_status_transition(client):
    response = client.post(
        "/tickets",
        json={
            "user_id": "test_user",
            "content": "测试非法状态流转",
        },
    )
    ticket_id = response.json()["id"]

    client.patch(
        f"/tickets/{ticket_id}/status",
        json={"status": "processing"},
    )

    response = client.patch(
        f"/tickets/{ticket_id}/status",
        json={"status": "pending"},
    )

    assert response.status_code == 409


def test_invalid_status_value(client):
    response = client.post(
        "/tickets",
        json={
            "user_id": "test_user",
            "content": "测试非法状态名称",
        },
    )
    ticket_id = response.json()["id"]

    response = client.patch(
        f"/tickets/{ticket_id}/status",
        json={"status": "unknown"},
    )

    assert response.status_code == 422


def test_resolved_is_terminal(client):
    response = client.post(
        "/tickets",
        json={
            "user_id": "test_user",
            "content": "测试终态约束",
        },
    )
    ticket_id = response.json()["id"]

    for next_status in ["processing", "resolved"]:
        response = client.patch(
            f"/tickets/{ticket_id}/status",
            json={"status": next_status},
        )
        assert response.status_code == 200

    response = client.patch(
        f"/tickets/{ticket_id}/status",
        json={"status": "pending"},
    )
    assert response.status_code == 409


def test_list_tickets_with_pagination(client):
    for i in range(3):
        response = client.post(
            "/tickets",
            json={
                "user_id": "test_user",
                "content": f"测试工单 {i}",
            },
        )
        assert response.status_code == 201

    response = client.get("/tickets?limit=2&offset=0")

    assert response.status_code == 200
    assert len(response.json()) == 2

    response = client.get("/tickets?limit=2&offset=2")

    assert response.status_code == 200
    assert len(response.json()) == 1


def test_filter_tickets_by_status(client):
    response = client.post(
        "/tickets",
        json={
            "user_id": "test_user",
            "content": "待处理工单",
        },
    )
    assert response.status_code == 201

    response = client.post(
        "/tickets",
        json={
            "user_id": "test_user",
            "content": "处理中工单",
        },
    )
    ticket_id = response.json()["id"]

    client.patch(
        f"/tickets/{ticket_id}/status",
        json={"status": "processing"},
    )

    response = client.get("/tickets?status=processing")

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["id"] == ticket_id


def test_invalid_pagination(client):
    response = client.get("/tickets?limit=0")
    assert response.status_code == 422


def test_ticket_event_created(client):
    response = client.post(
        "/tickets",
        json={
            "user_id": "event_test",
            "content": "测试操作历史",
        },
    )
    ticket_id = response.json()["id"]

    response = client.patch(
        f"/tickets/{ticket_id}/status",
        json={"status": "processing"},
    )
    assert response.status_code == 200

    response = client.get(f"/tickets/{ticket_id}/events")
    assert response.status_code == 200

    events = response.json()

    assert len(events) == 1
    assert events[0]["from_status"] == "pending"
    assert events[0]["to_status"] == "processing"
    assert events[0]["actor"] == "system"


def test_invalid_transition_does_not_create_event(client):
    response = client.post(
        "/tickets",
        json={
            "user_id": "event_test",
            "content": "测试非法操作不写历史",
        },
    )
    ticket_id = response.json()["id"]

    response = client.patch(
        f"/tickets/{ticket_id}/status",
        json={"status": "resolved"},
    )
    assert response.status_code == 409

    response = client.get(f"/tickets/{ticket_id}/events")
    assert response.status_code == 200
    assert response.json() == []


def test_ticket_events_are_isolated(client):
    ids = []

    for i in range(2):
        response = client.post(
            "/tickets",
            json={
                "user_id": "event_test",
                "content": f"工单 {i}",
            },
        )
        ids.append(response.json()["id"])

    response = client.patch(
        f"/tickets/{ids[0]}/status",
        json={"status": "processing"},
    )
    assert response.status_code == 200

    first_events = client.get(
        f"/tickets/{ids[0]}/events"
    ).json()

    second_events = client.get(
        f"/tickets/{ids[1]}/events"
    ).json()

    assert len(first_events) == 1
    assert second_events == []


def test_transaction_rollback_when_event_insert_fails(
    client,
    monkeypatch,
):
    from sqlalchemy.exc import SQLAlchemyError
    from app.models.ticket_event import TicketEvent
    from app.services import ticket_service

    # 先创建一条工单
    response = client.post(
        "/tickets",
        json={
            "user_id": "rollback_test",
            "content": "测试事务回滚",
        },
    )

    assert response.status_code == 201
    ticket_id = response.json()["id"]

    # 模拟事件写入时数据库发生异常
    def failing_commit(self):
        raise SQLAlchemyError("Simulated database failure")

    # 保存原始方法
    from sqlalchemy.orm import Session
    original_commit = Session.commit

    # 仅在事件存在时模拟失败
    def conditional_commit(self):
        has_event = any(
            isinstance(obj, TicketEvent)
            for obj in self.new
        )
        if has_event:
            return failing_commit(self)

        return original_commit(self)

    monkeypatch.setattr(
        Session,
        "commit",
        conditional_commit,
    )

    # API 调用会引发模拟异常
    with pytest.raises(SQLAlchemyError):
        client.patch(
            f"/tickets/{ticket_id}/status",
            json={"status": "processing"},
        )

    # 恢复 commit 方法，允许后续正常查询
    monkeypatch.setattr(
        Session,
        "commit",
        original_commit,
    )

    # 验证状态没有被错误更新
    response = client.get(f"/tickets/{ticket_id}")

    assert response.status_code == 200
    assert response.json()["status"] == "pending"

    # 验证没有留下不完整的操作历史
    response = client.get(f"/tickets/{ticket_id}/events")

    assert response.status_code == 200
    assert response.json() == []
