import io

import qrcode
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Ticket, User
from app.schemas import TicketOut
from app.services import tickets as tickets_service

router = APIRouter(prefix="/api/tickets", tags=["Билеты"])


def _check_access(ticket: Ticket, user: User) -> None:
    if ticket.user_id != user.id and user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Это не ваш билет")


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


@router.get("/{code}", response_model=TicketOut, summary="Билет по коду")
def get_ticket(
    code: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Ticket:
    ticket = tickets_service.get_by_code_or_404(db, code)
    _check_access(ticket, current_user)
    return ticket


@router.get(
    "/{code}/qr",
    response_class=StreamingResponse,
    summary="QR-код билета (картинка PNG)",
    responses={200: {"content": {"image/png": {}}}},
)
def ticket_qr(
    code: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    ticket = tickets_service.get_by_code_or_404(db, code)
    _check_access(ticket, current_user)

    image = qrcode.make(ticket.code)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="image/png")
