from datetime import datetime, timezone

from sqlalchemy import delete
from sqlalchemy.dialects.sqlite import insert

from app.models.processing_claim import ProcessingClaim


def acquire_claim(db, ticket_id, owner):
    """
    原子插入认领记录。
    调用者自行决定何时 commit。
    """
    statement = (
        insert(ProcessingClaim)
        .values(
            ticket_id=ticket_id,
            owner=owner,
            created_at=datetime.now(timezone.utc),
        )
        .on_conflict_do_nothing(
            index_elements=["ticket_id"]
        )
    )

    return db.execute(statement).rowcount == 1


def release_claim(db, ticket_id, owner):
    """
    只允许认领者释放自己的记录。
    调用者负责 commit。
    """
    statement = (
        delete(ProcessingClaim)
        .where(ProcessingClaim.ticket_id == ticket_id)
        .where(ProcessingClaim.owner == owner)
    )
    return db.execute(statement).rowcount


def claim_belongs_to(db, ticket_id, owner):
    claim = db.get(ProcessingClaim, ticket_id)
    return claim is not None and claim.owner == owner
