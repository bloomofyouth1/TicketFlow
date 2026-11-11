import logging
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.database import engine
from app.models.agent_task import AgentTask
from app.models.processing_claim import ProcessingClaim
from app.models.ticket_processing import TicketProcessingResult

logger = logging.getLogger("ticketflow.tasks")


def utc_now():
    return datetime.now(timezone.utc)


def recover_interrupted_tasks(bind=engine):
    """
    单进程服务启动恢复。

    前提：
    - 上一个服务实例已经停止；
    - 不存在其他正在执行的 Worker；
    - 不自动重新调用 LLM。
    """
    counts = {
        "interrupted": 0,
        "reconciled": 0,
        "released_claims": 0,
    }

    with Session(bind=bind) as db:
        try:
            tasks = db.scalars(
                select(AgentTask).where(
                    AgentTask.status.in_(
                        ["queued", "running"]
                    )
                )
            ).all()

            for task in tasks:
                result = db.get(
                    TicketProcessingResult,
                    task.ticket_id,
                )

                if result is not None:
                    # 工单结果已落库，只是任务终态未更新
                    task.status = "succeeded"
                    task.error_type = None
                    counts["reconciled"] += 1
                else:
                    task.status = "failed"
                    task.error_type = "InterruptedByRestart"
                    counts["interrupted"] += 1

                task.finished_at = utc_now()

            # 单实例重启时，旧进程的执行权全部失效
            deleted = db.execute(
                delete(ProcessingClaim)
            )
            counts["released_claims"] = deleted.rowcount

            db.commit()

        except Exception:
            db.rollback()
            raise

    logger.info(
        "Task recovery completed: %s",
        counts,
    )

    return counts
