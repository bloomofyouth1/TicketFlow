from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.ticket import Ticket
from app.models.ticket_event import TicketEvent
from app.models.ticket_processing import TicketProcessingResult
from app.models.ticket_review import TicketReview


router = APIRouter(
    prefix="/tickets",
    tags=["Ticket Reviews"],
)


class ReviewRequest(BaseModel):
    reviewer_id: str = Field(
        min_length=1, max_length=24
    )
    note: str = Field(
        min_length=1, max_length=2000
    )


class ReviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticket_id: str
    reviewer_id: str
    decision: str
    note: str
    from_status: str
    to_status: str
    created_at: datetime


def apply_review(
    db: Session,
    ticket_id: str,
    request: ReviewRequest,
    decision: str,
):
    ticket = db.get(Ticket, ticket_id)

    if ticket is None:
        raise HTTPException(
            status_code=404,
            detail="Ticket not found",
        )

    if decision in {"approve", "reject"}:
        expected_status = "processing"
        new_status = (
            "resolved"
            if decision == "approve"
            else "escalated"
        )
        processing = db.get(
            TicketProcessingResult, ticket_id
        )

        if (
            processing is None
            or processing.action != "suggest_reply"
        ):
            raise HTTPException(
                status_code=409,
                detail="No reviewable Agent suggestion",
            )

        if (
            decision == "approve"
            and not processing.suggested_reply
        ):
            raise HTTPException(
                status_code=409,
                detail="No suggested reply to approve",
            )

    elif decision == "resolve":
        expected_status = "escalated"
        new_status = "resolved"

    else:
        raise HTTPException(
            status_code=400,
            detail="Unsupported review decision",
        )

    if ticket.status != expected_status:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Review {decision} requires "
                f"status {expected_status}"
            ),
        )

    try:
        # 条件更新：避免两个并发审核同时成功改变状态
        changed = db.execute(
            update(Ticket)
            .where(Ticket.id == ticket_id)
            .where(Ticket.status == expected_status)
            .values(status=new_status)
        )

        if changed.rowcount != 1:
            db.rollback()
            raise HTTPException(
                status_code=409,
                detail="Ticket status changed concurrently",
            )

        review = TicketReview(
            ticket_id=ticket_id,
            reviewer_id=request.reviewer_id,
            decision=decision,
            note=request.note,
            from_status=expected_status,
            to_status=new_status,
        )

        event = TicketEvent(
            ticket_id=ticket_id,
            from_status=expected_status,
            to_status=new_status,
            actor=f"human:{request.reviewer_id}",
        )

        db.add(review)
        db.add(event)
        db.commit()
        db.refresh(review)

        return review

    except Exception:
        db.rollback()
        raise


@router.post(
    "/{ticket_id}/reviews/approve",
    response_model=ReviewResponse,
    status_code=201,
)
def approve_ticket(
    ticket_id: str,
    request: ReviewRequest,
    db: Session = Depends(get_db),
):
    return apply_review(
        db, ticket_id, request, "approve"
    )


@router.post(
    "/{ticket_id}/reviews/reject",
    response_model=ReviewResponse,
    status_code=201,
)
def reject_ticket(
    ticket_id: str,
    request: ReviewRequest,
    db: Session = Depends(get_db),
):
    return apply_review(
        db, ticket_id, request, "reject"
    )


@router.post(
    "/{ticket_id}/reviews/resolve",
    response_model=ReviewResponse,
    status_code=201,
)
def resolve_ticket(
    ticket_id: str,
    request: ReviewRequest,
    db: Session = Depends(get_db),
):
    return apply_review(
        db, ticket_id, request, "resolve"
    )


@router.get(
    "/{ticket_id}/reviews",
    response_model=list[ReviewResponse],
)
def list_reviews(
    ticket_id: str,
    db: Session = Depends(get_db),
):
    if db.get(Ticket, ticket_id) is None:
        raise HTTPException(
            status_code=404,
            detail="Ticket not found",
        )

    return db.scalars(
        select(TicketReview)
        .where(TicketReview.ticket_id == ticket_id)
        .order_by(TicketReview.id)
    ).all()
