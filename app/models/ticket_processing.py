from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class TicketProcessingResult(Base):
    __tablename__ = "ticket_processing_results"

    ticket_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tickets.id"),
        primary_key=True,
    )

    category: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    action: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    faq_id: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )

    suggested_reply: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    method: Mapped[str] = mapped_column(
        String(32),
        default="rule",
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
