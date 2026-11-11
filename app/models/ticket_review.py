from datetime import datetime, timezone

from sqlalchemy import (
    DateTime, ForeignKey, Integer, String, Text
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class TicketReview(Base):
    __tablename__ = "ticket_reviews"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    ticket_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tickets.id"),
        nullable=False, index=True
    )
    reviewer_id: Mapped[str] = mapped_column(
        String(32), nullable=False
    )
    decision: Mapped[str] = mapped_column(
        String(32), nullable=False
    )
    note: Mapped[str] = mapped_column(
        Text, nullable=False
    )
    from_status: Mapped[str] = mapped_column(
        String(32), nullable=False
    )
    to_status: Mapped[str] = mapped_column(
        String(32), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False
    )
