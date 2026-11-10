from app.models.agent_execution import AgentExecution
from app.core.logging_config import setup_logging
from fastapi import Depends, FastAPI, HTTPException, status
from sqlalchemy.orm import Session

from app.api.schemas import TicketCreate, TicketResponse
from app.core.database import Base, engine, get_db
from app.models.ticket import Ticket
from app.models.ticket_event import TicketEvent

# 第一版先自动建表，后续使用数据库迁移管理
from app.models.ticket_processing import TicketProcessingResult

Base.metadata.create_all(bind=engine)

setup_logging()

app = FastAPI(
    title="TicketFlow API",
    description="Enterprise AI Ticket Processing System",
    version="0.1.0",
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post(
    "/tickets",
    response_model=TicketResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_ticket(
    payload: TicketCreate,
    db: Session = Depends(get_db),
):
    ticket = Ticket(
        user_id=payload.user_id,
        content=payload.content,
        status="pending",
    )

    db.add(ticket)
    db.commit()
    db.refresh(ticket)

    return ticket


@app.get("/tickets/{ticket_id}", response_model=TicketResponse)
def get_ticket(
    ticket_id: str,
    db: Session = Depends(get_db),
):
    ticket = db.get(Ticket, ticket_id)

    if ticket is None:
        raise HTTPException(
            status_code=404,
            detail="Ticket not found",
        )

    return ticket

# Day 2: 工单列表查询
from typing import Optional

from fastapi import Query
from sqlalchemy import select


@app.get("/tickets", response_model=list[TicketResponse])
def list_tickets(
    status: Optional[str] = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    statement = select(Ticket)

    if status is not None:
        statement = statement.where(Ticket.status == status)

    statement = (
        statement
        .order_by(Ticket.created_at.desc(), Ticket.id.desc())
        .offset(offset)
        .limit(limit)
    )

    return db.scalars(statement).all()


from app.api.schemas import TicketStatusUpdate
from app.services.ticket_service import update_ticket_status


@app.patch(
    "/tickets/{ticket_id}/status",
    response_model=TicketResponse,
)
def change_ticket_status(
    ticket_id: str,
    payload: TicketStatusUpdate,
    db: Session = Depends(get_db),
):
    return update_ticket_status(
        db=db,
        ticket_id=ticket_id,
        new_status=payload.status,
    )


from app.api.schemas import TicketEventResponse


@app.get(
    "/tickets/{ticket_id}/events",
    response_model=list[TicketEventResponse],
)
def get_ticket_events(
    ticket_id: str,
    db: Session = Depends(get_db),
):
    ticket = db.get(Ticket, ticket_id)

    if ticket is None:
        raise HTTPException(
            status_code=404,
            detail="Ticket not found",
        )

    events = (
        db.query(TicketEvent)
        .filter(TicketEvent.ticket_id == ticket_id)
        .order_by(TicketEvent.id.asc())
        .all()
    )

    return events


from app.api.schemas import TicketProcessingResponse
from app.services.processing_service import process_ticket


@app.post(
    "/tickets/{ticket_id}/process",
    response_model=TicketProcessingResponse,
)
def process_ticket_endpoint(
    ticket_id: str,
    db: Session = Depends(get_db),
):
    return process_ticket(db, ticket_id)


@app.get(
    "/tickets/{ticket_id}/processing-result",
    response_model=TicketProcessingResponse,
)
def get_processing_result(
    ticket_id: str,
    db: Session = Depends(get_db),
):
    result = db.get(TicketProcessingResult, ticket_id)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Processing result not found",
        )

    return result
