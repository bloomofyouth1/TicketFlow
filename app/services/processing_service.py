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

    if mode == "agent":
        decision = run_resolution_agent(ticket.content)
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
        db.commit()
        db.refresh(result)

    except Exception:
        db.rollback()
        raise

    return result
