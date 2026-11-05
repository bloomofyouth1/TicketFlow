from fastapi import Depends, FastAPI, HTTPException, status
from sqlalchemy.orm import Session

from app.api.schemas import TicketCreate, TicketResponse
from app.core.database import Base, engine, get_db
from app.models.ticket import Ticket

# 第一版先自动建表，后续使用数据库迁移管理
Base.metadata.create_all(bind=engine)

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
