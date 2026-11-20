from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Ticket, User
from app.schemas import TicketOut

router = APIRouter(prefix="/api/tickets", tags=["Билеты"])


@router.get("", response_model=list[TicketOut], summary="Мои билеты")
def my_tickets(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Ticket]:
    return (
        db.scalars(
            select(Ticket)
            .options(selectinload(Ticket.event))
            .where(Ticket.user_id == current_user.id)
            .order_by(Ticket.id.desc())
        )
        .all()
    )
