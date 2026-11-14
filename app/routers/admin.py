from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_admin
from app.models import Booking, BookingStatus
from app.schemas import (
    BookingOut,
    EventCreate,
    EventOut,
    EventUpdate,
    Page,
    StatsOut,
)
from app.services import bookings as bookings_service
from app.services import events as events_service
from app.services import stats as stats_service

router = APIRouter(
    prefix="/api/admin",
    tags=["Администрирование"],
    dependencies=[Depends(get_current_admin)],
)


@router.post("/events", response_model=EventOut, status_code=201, summary="Создать мероприятие")
def create_event(data: EventCreate, db: Session = Depends(get_db)) -> EventOut:
    event = events_service.create_event(db, data)
    return events_service.build_event_out(event, taken=0)


@router.get("/events", response_model=Page[EventOut], summary="Все мероприятия (включая скрытые)")
def all_events(
    page: int = Query(1, ge=1),
    size: int = Query(settings.DEFAULT_PAGE_SIZE, ge=1, le=settings.MAX_PAGE_SIZE),
    db: Session = Depends(get_db),
) -> Page[EventOut]:
    events, taken, total = events_service.list_events(
        db, include_all=True, page=page, size=size
    )
    items = [events_service.build_event_out(event, taken.get(event.id, 0)) for event in events]
    return Page(
        items=items,
        total=total,
        page=page,
        size=size,
        pages=(total + size - 1) // size,
    )


@router.patch("/events/{event_id}", response_model=EventOut, summary="Изменить мероприятие")
def update_event(
    event_id: int,
    data: EventUpdate,
    db: Session = Depends(get_db),
) -> EventOut:
    changes = data.model_dump(exclude_unset=True)
    event = events_service.update_event(db, event_id, changes)
    taken = events_service.taken_map(db, [event.id]).get(event.id, 0)
    return events_service.build_event_out(event, taken)


@router.delete(
    "/events/{event_id}",
    status_code=204,
    summary="Удалить мероприятие",
)
def delete_event(event_id: int, db: Session = Depends(get_db)) -> None:
    events_service.delete_event(db, event_id)


@router.get("/bookings", response_model=Page[BookingOut], summary="Все брони портала")
def all_bookings(
    booking_status: BookingStatus | None = Query(None, alias="status", description="Фильтр по статусу"),
    page: int = Query(1, ge=1),
    size: int = Query(settings.DEFAULT_PAGE_SIZE, ge=1, le=settings.MAX_PAGE_SIZE),
    db: Session = Depends(get_db),
) -> Page[BookingOut]:
    bookings_service.sweep_expired_bookings(db)

    query = select(Booking)
    if booking_status:
        query = query.where(Booking.status == booking_status.value)

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    bookings = (
        db.scalars(
            query.options(selectinload(Booking.event), selectinload(Booking.tickets))
            .order_by(Booking.id.desc())
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


@router.get("/stats", response_model=StatsOut, summary="Статистика продаж")
def stats(db: Session = Depends(get_db)) -> StatsOut:
    return StatsOut(**stats_service.collect_stats(db))