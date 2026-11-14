import secrets
import threading

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import (
    Booking,
    BookingStatus,
    Event,
    Ticket,
    User,
    booking_deadline,
    utcnow,
)
from app.services.events import taken_map

_booking_lock = threading.Lock()


def sweep_expired_bookings(db: Session) -> int:
    result = db.execute(
        update(Booking)
        .where(
            Booking.status == BookingStatus.booked.value,
            Booking.expires_at < utcnow(),
        )
        .values(status=BookingStatus.expired.value)
    )
    db.commit()
    return result.rowcount or 0


def get_user_booking(db: Session, user: User, booking_id: int) -> Booking:
    booking = db.get(Booking, booking_id)
    if booking is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Бронь не найдена")
    if booking.user_id != user.id and user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Это не ваша бронь")
    return booking


def create_booking(db: Session, user: User, event_id: int, quantity: int) -> Booking:
    sweep_expired_bookings(db)

    with _booking_lock:
        event = db.get(Event, event_id)
        if event is None or not event.is_published:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Мероприятие не найдено")
        if event.starts_at <= utcnow():
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Мероприятие уже началось или прошло — бронирование недоступно",
            )

        taken = taken_map(db, [event.id]).get(event.id, 0)
        available = event.capacity - taken
        if quantity > available:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"Недостаточно свободных мест: доступно {available} из {event.capacity}",
            )

        booking = Booking(
            user_id=user.id,
            event_id=event.id,
            quantity=quantity,
            price_per_ticket=event.price,
            status=BookingStatus.booked.value,
            expires_at=booking_deadline(),
        )
        db.add(booking)
        db.commit()
        db.refresh(booking)
    return booking


def _generate_ticket_code(db: Session) -> str:
    for _ in range(10):
        code = "TKT-" + secrets.token_hex(5).upper()
        if db.scalar(select(Ticket.id).where(Ticket.code == code)) is None:
            return code
    raise HTTPException(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        "Не удалось сгенерировать уникальный код билета, попробуйте ещё раз",
    )


def confirm_booking(db: Session, booking: Booking) -> Booking:
    if booking.status == BookingStatus.confirmed.value:
        raise HTTPException(status.HTTP_409_CONFLICT, "Бронь уже подтверждена")

    if booking.status == BookingStatus.booked.value:
        if booking.expires_at <= utcnow():
            booking.status = BookingStatus.expired.value
            db.commit()
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "Время бронирования истекло, места освобождены — создайте бронь заново",
            )
    else:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Бронь со статусом «{booking.status}» нельзя подтвердить",
        )

    for _ in range(booking.quantity):
        db.add(
            Ticket(
                booking_id=booking.id,
                event_id=booking.event_id,
                user_id=booking.user_id,
                code=_generate_ticket_code(db),
            )
        )

    booking.status = BookingStatus.confirmed.value
    booking.confirmed_at = utcnow()
    db.commit()
    db.refresh(booking)
    return booking


def cancel_booking(db: Session, booking: Booking) -> Booking:
    if booking.status != BookingStatus.booked.value:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Отменить можно только неподтверждённую бронь (статус «{booking.status}»)",
        )

    booking.status = BookingStatus.cancelled.value
    db.commit()
    db.refresh(booking)
    return booking
