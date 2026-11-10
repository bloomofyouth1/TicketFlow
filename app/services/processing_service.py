import json
from app.models.agent_execution import AgentExecution
from app.agents.resolution_agent import run_resolution_agent
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.ticket import Ticket
from app.models.ticket_event import TicketEvent
from app.models.ticket_processing import TicketProcessingResult
import os
from app.agents.ticket_graph import run_ticket_graph
from app.agents.hybrid_ticket_graph import run_hybrid_ticket_graph


def process_ticket(db: Session, ticket_id: str):
    ticket = db.get(Ticket, ticket_id)

    if ticket is None:
        raise HTTPException(
            status_code=404,
            detail="Ticket not found",
        )

    existing = db.get(TicketProcessingResult, ticket_id)

    if existing is not None:
        return existing

    if ticket.status != "pending":
        raise HTTPException(
            status_code=409,
            detail="Only pending tickets can be processed",
        )

    mode = os.getenv("TICKETFLOW_ANALYZER", "rule")

    agent_outcome = None

    if mode == "agent":
        events = (
            db.query(TicketEvent)
            .filter(TicketEvent.ticket_id == ticket.id)
            .order_by(TicketEvent.id.asc())
            .all()
        )

        ticket_context = {
            "id": ticket.id,
            "status": ticket.status,
            "content": ticket.content,
        }

        history = [
            {
                "from_status": e.from_status,
                "to_status": e.to_status,
                "actor": e.actor,
            }
            for e in events
        ]

        agent_outcome = run_resolution_agent(
            ticket.content,
            ticket_context=ticket_context,
            history=history,
            return_outcome=True,
        )

        decision = agent_outcome.result
    elif mode == "llm":
        decision = run_hybrid_ticket_graph(ticket.content)
    elif mode == "rule":
        decision = run_ticket_graph(ticket.content)
    else:
        raise RuntimeError(
            f"Unsupported analyzer mode: {mode}"
        )

    if decision.action == "suggest_reply":
        new_status = "processing"
    elif decision.action == "escalate":
        new_status = "escalated"
    else:
        raise HTTPException(
            status_code=500,
            detail="Unsupported processing action",
        )

    result = TicketProcessingResult(
        ticket_id=ticket.id,
        category=decision.category,
        action=decision.action,
        faq_id=decision.faq_id,
        suggested_reply=decision.suggested_reply,
        reason=decision.reason,
        method=decision.method,
    )

    event = TicketEvent(
        ticket_id=ticket.id,
        from_status=ticket.status,
        to_status=new_status,
        actor="system",
    )

    try:
        ticket.status = new_status
        db.add(result)
        db.add(event)

        if agent_outcome is not None:
            db.add(AgentExecution(
                ticket_id=ticket.id,
                model_calls=agent_outcome.model_calls,
                tool_calls=agent_outcome.tool_calls,
                input_tokens=agent_outcome.input_tokens,
                output_tokens=agent_outcome.output_tokens,
                latency_seconds=agent_outcome.latency_seconds,
                tool_names=json.dumps(
                    agent_outcome.tool_names,
                    ensure_ascii=False,
                ),
                trace=json.dumps(
                    agent_outcome.trace,
                    ensure_ascii=False,
                ),
                error_type=agent_outcome.error_type,
                fallback=bool(agent_outcome.error_type),
            ))

        db.commit()
        db.refresh(result)

    except Exception:
        db.rollback()
        raise

    return result
