import json
import os
import uuid

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.agents.resolution_agent import run_resolution_agent
from app.agents.ticket_graph import run_ticket_graph
from app.agents.hybrid_ticket_graph import run_hybrid_ticket_graph
from app.models.agent_execution import AgentExecution
from app.models.ticket import Ticket
from app.models.ticket_event import TicketEvent
from app.models.ticket_processing import TicketProcessingResult
from app.services.processing_claim_service import (
    acquire_claim,
    claim_belongs_to,
    release_claim,
)


def process_ticket(
    db: Session,
    ticket_id: str,
    *,
    claim_owner: str | None = None,
):
    ticket = db.get(Ticket, ticket_id)

    if ticket is None:
        raise HTTPException(404, "Ticket not found")

    existing = db.get(TicketProcessingResult, ticket_id)

    if existing is not None:
        return existing

    if ticket.status != "pending":
        raise HTTPException(
            409, "Only pending tickets can be processed"
        )

    sync_claim = claim_owner is None

    if sync_claim:
        claim_owner = "sync:" + str(uuid.uuid4())

        if not acquire_claim(db, ticket_id, claim_owner):
            db.rollback()
            raise HTTPException(
                409, "Ticket processing already in progress"
            )

        # 在模型调用之前提交认领，避免长事务锁住数据库
        db.commit()

    elif not claim_belongs_to(db, ticket_id, claim_owner):
        raise HTTPException(
            409, "Task does not own ticket processing claim"
        )

    try:
        # 获得认领后重新读取状态，避免使用旧快照
        db.expire_all()
        ticket = db.get(Ticket, ticket_id)
        existing = db.get(TicketProcessingResult, ticket_id)

        if existing is not None:
            return existing

        if ticket is None or ticket.status != "pending":
            raise HTTPException(
                409, "Ticket is no longer pending"
            )

        mode = os.getenv("TICKETFLOW_ANALYZER", "rule")
        agent_outcome = None

        if mode == "agent":
            events = (
                db.query(TicketEvent)
                .filter(TicketEvent.ticket_id == ticket_id)
                .order_by(TicketEvent.id.asc())
                .all()
            )

            context = {
                "id": ticket.id,
                "status": ticket.status,
                "content": ticket.content,
            }

            history = [
                {
                    "from_status": event.from_status,
                    "to_status": event.to_status,
                    "actor": event.actor,
                }
                for event in events
            ]

            agent_outcome = run_resolution_agent(
                ticket.content,
                ticket_context=context,
                history=history,
                return_outcome=True,
            )
            decision = agent_outcome.result

        elif mode == "llm":
            decision = run_hybrid_ticket_graph(
                ticket.content
            )

        elif mode == "rule":
            decision = run_ticket_graph(ticket.content)

        else:
            raise RuntimeError(
                f"Unsupported analyzer mode: {mode}"
            )

        if decision.action == "suggest_reply":
            new_status = "processing"
        elif decision.action == "escalate":
            new_status = "escalated"
        else:
            raise HTTPException(
                500, "Unsupported processing action"
            )

        result = TicketProcessingResult(
            ticket_id=ticket.id,
            category=decision.category,
            action=decision.action,
            faq_id=decision.faq_id,
            suggested_reply=decision.suggested_reply,
            reason=decision.reason,
            method=decision.method,
        )

        event = TicketEvent(
            ticket_id=ticket.id,
            from_status=ticket.status,
            to_status=new_status,
            actor="system",
        )

        ticket.status = new_status
        db.add(result)
        db.add(event)

        if agent_outcome is not None:
            db.add(AgentExecution(
                ticket_id=ticket.id,
                model_calls=agent_outcome.model_calls,
                tool_calls=agent_outcome.tool_calls,
                input_tokens=agent_outcome.input_tokens,
                output_tokens=agent_outcome.output_tokens,
                latency_seconds=agent_outcome.latency_seconds,
                tool_names=json.dumps(
                    agent_outcome.tool_names,
                    ensure_ascii=False,
                ),
                trace=json.dumps(
                    agent_outcome.trace,
                    ensure_ascii=False,
                ),
                error_type=agent_outcome.error_type,
                fallback=bool(agent_outcome.error_type),
            ))

        db.commit()
        db.refresh(result)
        return result

    except Exception:
        db.rollback()
        raise

    finally:
        if sync_claim:
            # 释放同步认领。异步认领由 Worker 负责释放。
            try:
                db.rollback()
                release_claim(db, ticket_id, claim_owner)
                db.commit()
            except Exception:
                db.rollback()
                raise
