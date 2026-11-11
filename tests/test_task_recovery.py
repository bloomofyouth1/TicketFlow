from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.database import Base
from app.models.ticket import Ticket
from app.models.agent_task import AgentTask
from app.models.processing_claim import ProcessingClaim
from app.models.ticket_processing import TicketProcessingResult
from app.services.task_recovery import recover_interrupted_tasks


def make_database(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'recovery.db'}",
    )

    Base.metadata.create_all(engine)

    return engine


def add_ticket(db, ticket_id):
    db.add(Ticket(
        id=ticket_id,
        user_id="recovery_test",
        content="忘记密码，怎么重置密码？",
        status="pending",
    ))


def test_running_task_recovered_as_failed(tmp_path):
    engine = make_database(tmp_path)

    with Session(engine) as db:
        add_ticket(db, "ticket-001")
        db.add(AgentTask(
            id="task-001",
            ticket_id="ticket-001",
            status="running",
        ))
        db.add(ProcessingClaim(
            ticket_id="ticket-001",
            owner="task-001",
        ))
        db.commit()

    result = recover_interrupted_tasks(engine)

    assert result["interrupted"] == 1
    assert result["released_claims"] == 1

    with Session(engine) as db:
        task = db.get(AgentTask, "task-001")
        assert task.status == "failed"
        assert task.error_type == "InterruptedByRestart"
        assert task.finished_at is not None
        assert db.get(
            ProcessingClaim, "ticket-001"
        ) is None


def test_queued_task_recovered_as_failed(tmp_path):
    engine = make_database(tmp_path)

    with Session(engine) as db:
        add_ticket(db, "ticket-002")
        db.add(AgentTask(
            id="task-002",
            ticket_id="ticket-002",
            status="queued",
        ))
        db.commit()

    result = recover_interrupted_tasks(engine)

    assert result["interrupted"] == 1

    with Session(engine) as db:
        task = db.get(AgentTask, "task-002")
        assert task.status == "failed"


def test_completed_processing_is_reconciled(tmp_path):
    engine = make_database(tmp_path)

    with Session(engine) as db:
        add_ticket(db, "ticket-003")
        db.add(AgentTask(
            id="task-003",
            ticket_id="ticket-003",
            status="running",
        ))
        db.add(TicketProcessingResult(
            ticket_id="ticket-003",
            category="account",
            action="suggest_reply",
            faq_id="FAQ-001",
            suggested_reply="请通过邮箱重置密码",
            reason="Approved FAQ",
            method="agent_guarded",
        ))
        db.commit()

    result = recover_interrupted_tasks(engine)

    assert result["reconciled"] == 1

    with Session(engine) as db:
        task = db.get(AgentTask, "task-003")
        assert task.status == "succeeded"
        assert task.error_type is None


def test_recovery_is_repeatable(tmp_path):
    engine = make_database(tmp_path)

    with Session(engine) as db:
        add_ticket(db, "ticket-004")
        db.add(AgentTask(
            id="task-004",
            ticket_id="ticket-004",
            status="running",
        ))
        db.commit()

    first = recover_interrupted_tasks(engine)
    second = recover_interrupted_tasks(engine)

    assert first["interrupted"] == 1
    assert second["interrupted"] == 0
    assert second["reconciled"] == 0
