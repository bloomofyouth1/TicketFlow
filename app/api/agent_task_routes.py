from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.agent_task import AgentTask
from app.services.agent_task_service import submit_agent_task


router = APIRouter(tags=["Agent Tasks"])


class AgentTaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    ticket_id: str
    status: str
    error_type: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


@router.post(
    "/tickets/{ticket_id}/process-async",
    response_model=AgentTaskResponse,
)
def create_agent_task(
    ticket_id: str,
    response: Response,
    db: Session = Depends(get_db),
):
    task, created = submit_agent_task(db, ticket_id)

    if created:
        response.status_code = 202

    return task


@router.get(
    "/agent-tasks/{task_id}",
    response_model=AgentTaskResponse,
)
def get_agent_task(
    task_id: str,
    db: Session = Depends(get_db),
):
    task = db.get(AgentTask, task_id)
    if task is None:
        raise HTTPException(404, "Agent task not found")

    return task
