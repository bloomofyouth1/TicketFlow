from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.ticket import Ticket
from app.models.ticket_event import TicketEvent


ALLOWED_TRANSITIONS = {
    "pending": {"processing", "escalated"},
    "processing": {"resolved", "escalated"},
    "escalated": {"processing", "resolved"},
    "resolved": set(),
}


def update_ticket_status(
    db: Session,
    ticket_id: str,
    new_status: str,
    actor: str = "system",
) -> Ticket:
    ticket = db.get(Ticket, ticket_id)

    if ticket is None:
        raise HTTPException(
            status_code=404,
            detail="Ticket not found",
        )

    old_status = ticket.status
    allowed = ALLOWED_TRANSITIONS.get(old_status, set())

    if new_status not in allowed:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Invalid status transition: "
                f"{old_status} -> {new_status}"
            ),
        )

    event = TicketEvent(
        ticket_id=ticket.id,
        from_status=old_status,
        to_status=new_status,
        actor=actor,
    )

    try:
        ticket.status = new_status
        db.add(event)

        # 只提交一次，保持状态与历史一致
        db.commit()
        db.refresh(ticket)

    except Exception:
        db.rollback()
        raise

    return ticket
