import threading
import time

import pytest

from app.services import agent_task_service


@pytest.fixture(autouse=True)
def rule_mode(monkeypatch):
    monkeypatch.setenv("TICKETFLOW_ANALYZER", "rule")


def create_ticket(client, content="忘记密码，怎么重置密码？"):
    response = client.post(
        "/tickets",
        json={
            "user_id": "async_test",
            "content": content,
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def wait_task(client, task_id, timeout=5.0):
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        response = client.get(
            f"/agent-tasks/{task_id}"
        )
        assert response.status_code == 200

        task = response.json()

        if task["status"] in {"succeeded", "failed"}:
            return task

        time.sleep(0.02)

    raise AssertionError("Async task did not finish")


def test_async_task_success_and_deduplication(client):
    ticket_id = create_ticket(client)

    first = client.post(
        f"/tickets/{ticket_id}/process-async"
    )
    assert first.status_code == 202

    task_id = first.json()["id"]

    second = client.post(
        f"/tickets/{ticket_id}/process-async"
    )
    assert second.status_code == 200
    assert second.json()["id"] == task_id

    done = wait_task(client, task_id)
    assert done["status"] == "succeeded"

    ticket = client.get(
        f"/tickets/{ticket_id}"
    ).json()
    assert ticket["status"] == "processing"

    events = client.get(
        f"/tickets/{ticket_id}/events"
    ).json()
    assert len(events) == 1


def test_async_task_failure_is_recorded(
    client, monkeypatch
):
    def failing_processor(db, ticket_id):
        raise RuntimeError("Simulated failure")

    monkeypatch.setattr(
        agent_task_service,
        "process_ticket",
        failing_processor,
    )

    ticket_id = create_ticket(client)

    submitted = client.post(
        f"/tickets/{ticket_id}/process-async"
    )
    assert submitted.status_code == 202

    done = wait_task(client, submitted.json()["id"])
    assert done["status"] == "failed"
    assert done["error_type"] == "RuntimeError"

    ticket = client.get(
        f"/tickets/{ticket_id}"
    ).json()
    assert ticket["status"] == "pending"


def test_task_capacity_limit(client, monkeypatch):
    release = threading.Event()
    started = threading.Event()

    def blocking_processor(db, ticket_id):
        started.set()
        if not release.wait(timeout=4):
            raise TimeoutError("Test worker timeout")
        return None

    monkeypatch.setattr(
        agent_task_service,
        "process_ticket",
        blocking_processor,
    )

    task_ids = []

    try:
        for _ in range(4):
            ticket_id = create_ticket(client)

            response = client.post(
                f"/tickets/{ticket_id}/process-async"
            )
            assert response.status_code == 202
            task_ids.append(response.json()["id"])

        assert started.wait(timeout=2)

        overflow_ticket = create_ticket(client)
        overflow = client.post(
            f"/tickets/{overflow_ticket}/process-async"
        )
        assert overflow.status_code == 503

    finally:
        release.set()

    for task_id in task_ids:
        done = wait_task(client, task_id)
        assert done["status"] == "succeeded"


def test_missing_task(client):
    response = client.get(
        "/agent-tasks/nonexistent"
    )
    assert response.status_code == 404
