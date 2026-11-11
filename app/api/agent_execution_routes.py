import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.ticket import Ticket
from app.models.agent_execution import AgentExecution


router = APIRouter(tags=["Agent Execution"])


class AgentExecutionResponse(BaseModel):
    ticket_id: str
    model_calls: int
    tool_calls: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    latency_seconds: float
    tool_names: list[str]
    trace: list[str]
    error_type: str | None
    fallback: bool


@router.get(
    "/tickets/{ticket_id}/agent-execution",
    response_model=AgentExecutionResponse,
)
def get_agent_execution(
    ticket_id: str,
    db: Session = Depends(get_db),
):
    if db.get(Ticket, ticket_id) is None:
        raise HTTPException(
            status_code=404,
            detail="Ticket not found",
        )

    run = db.get(AgentExecution, ticket_id)

    if run is None:
        raise HTTPException(
            status_code=404,
            detail="Agent execution not available",
        )

    return AgentExecutionResponse(
        ticket_id=run.ticket_id,
        model_calls=run.model_calls,
        tool_calls=run.tool_calls,
        input_tokens=run.input_tokens,
        output_tokens=run.output_tokens,
        total_tokens=(
            run.input_tokens + run.output_tokens
        ),
        latency_seconds=run.latency_seconds,
        tool_names=json.loads(run.tool_names),
        trace=json.loads(run.trace),
        error_type=run.error_type,
        fallback=run.fallback,
    )
