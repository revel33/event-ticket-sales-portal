from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session, selectinload

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models import Booking, User
from app.schemas import BookingCreate, BookingOut, Page
from app.services import bookings as bookings_service

router = APIRouter(prefix="/api/bookings", tags=["Брони"])


@router.post(
    "",
    response_model=BookingOut,
    status_code=201,
    summary="Забронировать билеты",
)
def create_booking(
    data: BookingCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Booking:
    return bookings_service.create_booking(db, current_user, data.event_id, data.quantity)


@router.get("", response_model=Page[BookingOut], summary="Мои брони")
def my_bookings(
    page: int = Query(1, ge=1),
    size: int = Query(settings.DEFAULT_PAGE_SIZE, ge=1, le=settings.MAX_PAGE_SIZE),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Page[BookingOut]:
    bookings_service.sweep_expired_bookings(db)

    query = select(Booking).where(Booking.user_id == current_user.id)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    bookings = (
        db.scalars(
            query.options(selectinload(Booking.event), selectinload(Booking.tickets))
            .order_by(desc(Booking.created_at))
            .offset((page - 1) * size)
            .limit(size)
        )
        .all()
    )
    return Page(
        items=bookings,
        total=total,
        page=page,
        size=size,
        pages=(total + size - 1) // size,
    )


@router.get("/{booking_id}", response_model=BookingOut, summary="Бронь по id")
def get_booking(
    booking_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Booking:
    return bookings_service.get_user_booking(db, current_user, booking_id)


@router.post("/{booking_id}/confirm", response_model=BookingOut, summary="Подтвердить бронь")
def confirm_booking(
    booking_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Booking:
    booking = bookings_service.get_user_booking(db, current_user, booking_id)
    return bookings_service.confirm_booking(db, booking)


@router.post("/{booking_id}/cancel", response_model=BookingOut, summary="Отменить бронь")
def cancel_booking(
    booking_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Booking:
    booking = bookings_service.get_user_booking(db, current_user, booking_id)
    return bookings_service.cancel_booking(db, booking)
