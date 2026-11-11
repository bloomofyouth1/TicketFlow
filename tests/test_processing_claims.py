import threading
import time

import pytest

from app.services import processing_service


@pytest.fixture(autouse=True)
def rule_mode(monkeypatch):
    monkeypatch.setenv(
        "TICKETFLOW_ANALYZER", "rule"
    )


def new_ticket(client):
    response = client.post(
        "/tickets",
        json={
            "user_id": "claim_test",
            "content": "忘记密码，怎么重置密码？",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def wait_for_task(client, task_id):
    for _ in range(150):
        response = client.get(
            f"/agent-tasks/{task_id}"
        )
        assert response.status_code == 200

        task = response.json()

        if task["status"] in {
            "succeeded", "failed"
        }:
            return task

        time.sleep(0.02)

    raise AssertionError("Task did not finish")


def install_slow_processor(monkeypatch):
    entered = threading.Event()
    release = threading.Event()
    original = processing_service.run_ticket_graph

    def slow(content):
        entered.set()
        if not release.wait(timeout=5):
            raise TimeoutError("Test timed out")
        return original(content)

    monkeypatch.setattr(
        processing_service,
        "run_ticket_graph",
        slow,
    )
    return entered, release


def test_two_synchronous_requests_do_not_overlap(
    client, monkeypatch
):
    entered, release = install_slow_processor(
        monkeypatch
    )
    ticket_id = new_ticket(client)
    responses = []

    def first_request():
        responses.append(
            client.post(
                f"/tickets/{ticket_id}/process"
            )
        )

    thread = threading.Thread(target=first_request)
    thread.start()

    try:
        assert entered.wait(timeout=3)

        second = client.post(
            f"/tickets/{ticket_id}/process"
        )
        assert second.status_code == 409
    finally:
        release.set()
        thread.join(timeout=5)

    assert not thread.is_alive()
    assert len(responses) == 1
    assert responses[0].status_code == 200

    events = client.get(
        f"/tickets/{ticket_id}/events"
    ).json()
    assert len(events) == 1


def test_async_job_blocks_direct_processing(
    client, monkeypatch
):
    entered, release = install_slow_processor(
        monkeypatch
    )
    ticket_id = new_ticket(client)

    submitted = client.post(
        f"/tickets/{ticket_id}/process-async"
    )
    assert submitted.status_code == 202
    task_id = submitted.json()["id"]

    try:
        assert entered.wait(timeout=3)

        direct = client.post(
            f"/tickets/{ticket_id}/process"
        )
        assert direct.status_code == 409

        repeated = client.post(
            f"/tickets/{ticket_id}/process-async"
        )
        assert repeated.json()["id"] == task_id
    finally:
        release.set()

    task = wait_for_task(client, task_id)
    assert task["status"] == "succeeded"


def test_direct_processing_blocks_async_submission(
    client, monkeypatch
):
    entered, release = install_slow_processor(
        monkeypatch
    )
    ticket_id = new_ticket(client)
    responses = []

    def direct_request():
        responses.append(
            client.post(
                f"/tickets/{ticket_id}/process"
            )
        )

    thread = threading.Thread(target=direct_request)
    thread.start()

    try:
        assert entered.wait(timeout=3)

        submitted = client.post(
            f"/tickets/{ticket_id}/process-async"
        )
        assert submitted.status_code == 409
    finally:
        release.set()
        thread.join(timeout=5)

    assert not thread.is_alive()
    assert responses[0].status_code == 200
