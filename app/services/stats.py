from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.models import Booking, Event, Ticket, User


def collect_stats(db: Session) -> dict:
    total_users = db.scalar(select(func.count(User.id))) or 0
    total_events = db.scalar(select(func.count(Event.id))) or 0
    tickets_sold = db.scalar(select(func.count(Ticket.id))) or 0

    revenue = db.scalar(
        select(
            func.coalesce(
                func.sum(Booking.quantity * Booking.price_per_ticket), 0
            )
        ).where(Booking.status == "confirmed")
    ) or 0

    status_rows = db.execute(
        select(Booking.status, func.count(Booking.id)).group_by(Booking.status)
    ).all()
    bookings_by_status = {row[0]: row[1] for row in status_rows}

    top_rows = db.execute(
        select(
            Event.id,
            Event.title,
            func.sum(Booking.quantity).label("sold"),
            func.sum(Booking.quantity * Booking.price_per_ticket).label("money"),
        )
        .join(Booking, Event.id == Booking.event_id)
        .where(Booking.status == "confirmed")
        .group_by(Event.id, Event.title)
        .order_by(desc("sold"))
        .limit(10)
    ).all()

    top_events = [
        {
            "event_id": event_id,
            "title": title,
            "tickets_sold": int(sold or 0),
            "revenue": int(money or 0),
        }
        for event_id, title, sold, money in top_rows
    ]

    return {
        "total_users": total_users,
        "total_events": total_events,
        "bookings_by_status": bookings_by_status,
        "tickets_sold": tickets_sold,
        "revenue": revenue,
        "top_events": top_events,
    }
