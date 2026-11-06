from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.ticket import Ticket


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
) -> Ticket:
    ticket = db.get(Ticket, ticket_id)

    if ticket is None:
        raise HTTPException(
            status_code=404,
            detail="Ticket not found",
        )

    allowed = ALLOWED_TRANSITIONS.get(ticket.status, set())

    if new_status not in allowed:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Invalid status transition: "
                f"{ticket.status} -> {new_status}"
            ),
        )

    ticket.status = new_status
    db.commit()
    db.refresh(ticket)

    return ticket
