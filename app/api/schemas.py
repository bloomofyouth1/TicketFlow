from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TicketCreate(BaseModel):
    user_id: str = Field(min_length=1, max_length=64)
    content: str = Field(min_length=1, max_length=5000)


class TicketResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    content: str
    status: str
    created_at: datetime


from typing import Literal


class TicketStatusUpdate(BaseModel):
    status: Literal[
        "pending",
        "processing",
        "escalated",
        "resolved",
    ]


class TicketEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticket_id: str
    from_status: str
    to_status: str
    actor: str
    created_at: datetime
