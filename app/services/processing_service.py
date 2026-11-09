from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.ticket import Ticket
from app.models.ticket_event import TicketEvent
from app.models.ticket_processing import TicketProcessingResult
from app.services.ticket_processor import process_ticket_content


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

    decision = process_ticket_content(ticket.content)

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
