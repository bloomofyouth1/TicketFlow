from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class AgentExecution(Base):
    __tablename__ = "agent_executions"

    ticket_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tickets.id"),
        primary_key=True,
    )

    model_calls: Mapped[int] = mapped_column(
        Integer, nullable=False
    )

    tool_calls: Mapped[int] = mapped_column(
        Integer, nullable=False
    )

    input_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False
    )

    output_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False
    )

    latency_seconds: Mapped[float] = mapped_column(
        Float, nullable=False
    )

    tool_names: Mapped[str] = mapped_column(
        Text, nullable=False
    )

    trace: Mapped[str] = mapped_column(
        Text, nullable=False
    )

    error_type: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )

    fallback: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
