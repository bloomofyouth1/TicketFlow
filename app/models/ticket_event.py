from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class TicketEvent(Base):
    __tablename__ = "ticket_events"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    ticket_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tickets.id"),
        nullable=False,
        index=True,
    )

    from_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    to_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    actor: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="system",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
