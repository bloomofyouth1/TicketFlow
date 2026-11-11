import logging
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session

from app.models.agent_task import AgentTask
from app.models.ticket import Ticket
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


def _mark_failed(session, task_id, error_type):
    task = session.get(AgentTask, task_id)
    if task is None:
        return

    task.status = "failed"
    task.error_type = error_type[:128]
    task.finished_at = utc_now()
    session.commit()


def _run_job(task_id, bind):
    # 每个任务创建自己的数据库会话
    try:
        with Session(bind=bind, expire_on_commit=False) as db:
            try:
                job = db.get(AgentTask, task_id)

                if job is None or job.status != "queued":
                    return

                job.status = "running"
                job.started_at = utc_now()
                db.commit()

                # 复用已有的 Agent + 工单处理服务
                process_ticket(db, job.ticket_id)

                job = db.get(AgentTask, task_id)
                job.status = "succeeded"
                job.finished_at = utc_now()
                db.commit()

            except Exception as exc:
                db.rollback()
                error_type = type(exc).__name__

                logger.exception(
                    "Agent task failed: task_id=%s",
                    task_id,
                )

                try:
                    _mark_failed(db, task_id, error_type)
                except Exception:
                    db.rollback()
                    logger.exception(
                        "Could not persist task failure"
                    )

    finally:
        capacity.release()


def submit_agent_task(db: Session, ticket_id: str):
    ticket = db.get(Ticket, ticket_id)

    if ticket is None:
        raise HTTPException(404, "Ticket not found")

    existing = db.scalar(
        select(AgentTask).where(
            AgentTask.ticket_id == ticket_id
        )
    )
    if existing is not None:
        return existing, False

    if ticket.status != "pending":
        raise HTTPException(
            409, "Only pending tickets can be submitted"
        )

    if not capacity.acquire(blocking=False):
        db.expire_all()
        existing = db.scalar(
            select(AgentTask).where(
                AgentTask.ticket_id == ticket_id
            )
        )
        if existing is not None:
            return existing, False
        raise HTTPException(
            503, "Agent task capacity reached"
        )

    owned_capacity = True

    try:
        task_id = str(uuid.uuid4())

        stmt = (
            insert(AgentTask)
            .values(
                id=task_id,
                ticket_id=ticket_id,
                status="queued",
                created_at=utc_now(),
            )
            .on_conflict_do_nothing(
                index_elements=["ticket_id"]
            )
        )
        inserted = db.execute(stmt)
        db.commit()

        if inserted.rowcount != 1:
            db.expire_all()
            existing = db.scalar(
                select(AgentTask).where(
                    AgentTask.ticket_id == ticket_id
                )
            )
            if existing is None:
                raise RuntimeError(
                    "Conflicting task not found"
                )
            return existing, False

        try:
            executor.submit(
                _run_job,
                task_id,
                db.get_bind(),
            )
            # 容量归后台执行器管理
            owned_capacity = False
        except Exception as exc:
            _mark_failed(
                db, task_id, type(exc).__name__
            )

        return db.get(AgentTask, task_id), True

    except Exception:
        db.rollback()
        raise

    finally:
        if owned_capacity:
            capacity.release()
