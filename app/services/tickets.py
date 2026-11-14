from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Ticket


def get_by_code_or_404(db: Session, code: str) -> Ticket:
    ticket = db.scalar(select(Ticket).where(Ticket.code == code))
    if ticket is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Билет не найден")
    return ticket
