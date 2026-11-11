import logging
import threading
import uuid

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.agent_task import AgentTask
from app.models.ticket import Ticket
from app.services.processing_claim_service import (
    acquire_claim,
    release_claim,
)
from app.services.processing_service import process_ticket


logger = logging.getLogger("ticketflow.tasks")

MAX_WORKERS = 2
MAX_INFLIGHT = 4

executor = ThreadPoolExecutor(
    max_workers=MAX_WORKERS,
    thread_name_prefix="ticket-agent",
)

capacity = threading.BoundedSemaphore(MAX_INFLIGHT)


def utc_now():
    return datetime.now(timezone.utc)


def find_task(db, ticket_id):
    return db.scalar(
        select(AgentTask)
        .where(AgentTask.ticket_id == ticket_id)
    )


def mark_failed(db, task_id, error_type):
    task = db.get(AgentTask, task_id)

    if task is not None:
        task.status = "failed"
        task.error_type = error_type[:128]
        task.finished_at = utc_now()
        db.commit()


def _run_job(task_id, bind):
    ticket_id = None

    try:
        with Session(
            bind=bind,
            expire_on_commit=False,
        ) as db:
            try:
                task = db.get(AgentTask, task_id)

                if task is None:
                    return

                ticket_id = task.ticket_id

                if task.status != "queued":
                    return

                task.status = "running"
                task.started_at = utc_now()
                db.commit()

                process_ticket(
                    db,
                    ticket_id,
                    claim_owner=task_id,
                )

                task = db.get(AgentTask, task_id)
                task.status = "succeeded"
                task.finished_at = utc_now()
                db.commit()

            except Exception as exc:
                db.rollback()
                logger.error(
                    "Agent task failed: %s",
                    type(exc).__name__,
                )

                try:
                    mark_failed(
                        db, task_id, type(exc).__name__
                    )
                except Exception:
                    db.rollback()
                    logger.exception(
                        "Could not persist failed task"
                    )

    finally:
        # 无论成功或失败，都释放此任务的认领。
        # 使用独立 Session，避免复用已失败的事务。
        if ticket_id is not None:
            try:
                with Session(bind=bind) as cleanup:
                    release_claim(
                        cleanup,
                        ticket_id,
                        task_id,
                    )
                    cleanup.commit()
            except Exception:
                logger.exception(
                    "Could not release processing claim"
                )

        capacity.release()


def submit_agent_task(db: Session, ticket_id: str):
    ticket = db.get(Ticket, ticket_id)

    if ticket is None:
        raise HTTPException(404, "Ticket not found")

    existing = find_task(db, ticket_id)

    if existing is not None:
        return existing, False

    if ticket.status != "pending":
        raise HTTPException(
            409, "Only pending tickets can be submitted"
        )

    if not capacity.acquire(blocking=False):
        db.expire_all()
        existing = find_task(db, ticket_id)

        if existing is not None:
            return existing, False

        raise HTTPException(
            503, "Agent task capacity reached"
        )

    owned_capacity = True

    try:
        task_id = str(uuid.uuid4())

        # 先认领再创建任务，两次写入在同一事务内提交
        if not acquire_claim(db, ticket_id, task_id):
            db.rollback()
            existing = find_task(db, ticket_id)

            if existing is not None:
                return existing, False

            raise HTTPException(
                409, "Ticket processing already in progress"
            )

        task = AgentTask(
            id=task_id,
            ticket_id=ticket_id,
            status="queued",
            created_at=utc_now(),
        )

        db.add(task)
        db.commit()

        try:
            executor.submit(
                _run_job,
                task_id,
                db.get_bind(),
            )
            owned_capacity = False

        except Exception as exc:
            db.rollback()
            try:
                mark_failed(
                    db, task_id, type(exc).__name__
                )
                release_claim(
                    db, ticket_id, task_id
                )
                db.commit()
            except Exception:
                db.rollback()
                raise

        return db.get(AgentTask, task_id), True

    except Exception:
        db.rollback()
        raise

    finally:
        if owned_capacity:
            capacity.release()
