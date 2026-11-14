from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import Booking, Event, EventCategory, utcnow
from app.schemas import EventCreate, EventOut, EventUpdate

_ACTIVE_STATUSES_QUERY = (
    select(
        Booking.event_id,
        func.sum(Booking.quantity).label("taken"),
    )
    .where(
        or_(
            Booking.status == "confirmed",
            (Booking.status == "booked") & (Booking.expires_at > utcnow()),
        )
    )
    .group_by(Booking.event_id)
)


def taken_map(db: Session, event_ids: list[int]) -> dict[int, int]:
    if not event_ids:
        return {}

    subquery = _ACTIVE_STATUSES_QUERY.subquery()
    rows = db.execute(
        select(subquery.c.event_id, subquery.c.taken).where(subquery.c.event_id.in_(event_ids))
    ).all()
    return {event_id: int(taken or 0) for event_id, taken in rows}


def build_event_out(event: Event, taken: int) -> EventOut:
    out = EventOut.model_validate(event)
    out.available = max(event.capacity - taken, 0)
    return out


def list_events(
    db: Session,
    *,
    q: str | None = None,
    city: str | None = None,
    category: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    available_only: bool = False,
    include_all: bool = False,
    page: int = 1,
    size: int = 10,
) -> tuple[list[Event], dict[int, int], int]:
    query = select(Event)
    if not include_all:
        query = query.where(Event.is_published.is_(True), Event.starts_at > utcnow())

    if q:
        pattern = f"%{q}%"
        query = query.where(
            or_(
                Event.title.ilike(pattern),
                Event.description.ilike(pattern),
                Event.venue.ilike(pattern),
            )
        )
    if city:
        query = query.where(Event.city == city)
    if category:
        query = query.where(Event.category == category)
    if date_from:
        query = query.where(Event.starts_at >= date_from)
    if date_to:
        query = query.where(Event.starts_at <= date_to)

    if available_only:
        subquery = _ACTIVE_STATUSES_QUERY.subquery()
        taken = func.coalesce(subquery.c.taken, 0)
        query = (
            query
            .outerjoin(subquery, Event.id == subquery.c.event_id)
            .where(Event.capacity - taken > 0)
        )

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    events = (
        db.scalars(query.order_by(Event.starts_at.asc()).offset((page - 1) * size).limit(size))
        .all()
    )
    taken_per_event = taken_map(db, [event.id for event in events])
    return list(events), taken_per_event, total


def list_cities(db: Session) -> list[str]:
    rows = db.execute(
        select(Event.city)
        .where(Event.is_published.is_(True), Event.starts_at > utcnow())
        .distinct()
        .order_by(Event.city)
    ).all()
    return [row[0] for row in rows]


def create_event(db: Session, data: EventCreate) -> Event:
    if data.starts_at <= utcnow():
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Дата мероприятия должна быть в будущем",
        )

    event = Event(
        title=data.title,
        description=data.description,
        category=data.category.value,
        venue=data.venue,
        city=data.city,
        starts_at=data.starts_at,
        price=data.price,
        capacity=data.capacity,
        image_url=data.image_url,
        is_published=True,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def update_event(db: Session, event_id: int, changes: dict) -> Event:
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Мероприятие не найдено")
    if not changes:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Не передано ни одного поля для изменения",
        )

    if isinstance(changes.get("category"), EventCategory):
        changes["category"] = changes["category"].value

    if "starts_at" in changes and changes["starts_at"] <= utcnow():
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Дата мероприятия должна быть в будущем",
        )

    if "capacity" in changes:
        taken = taken_map(db, [event.id]).get(event.id, 0)
        if changes["capacity"] < taken:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"Нельзя уменьшить вместимость: уже занято {taken} мест",
            )

    for field, value in changes.items():
        setattr(event, field, value)

    db.commit()
    db.refresh(event)
    return event


def delete_event(db: Session, event_id: int) -> None:
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Мероприятие не найдено")

    taken = taken_map(db, [event.id]).get(event.id, 0)
    if taken > 0:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Нельзя удалить мероприятие с активными бронями (занято {taken} мест)",
        )

    db.delete(event)
    db.commit()
