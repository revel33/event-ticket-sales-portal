from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Event, EventCategory
from app.schemas import EventOut, Page
from app.services import events as events_service

router = APIRouter(prefix="/api/events", tags=["Мероприятия"])


@router.get("", response_model=Page[EventOut], summary="Каталог мероприятий")
def list_events(
    q: str | None = Query(None, description="Поиск по названию, описанию и месту"),
    city: str | None = Query(None, description="Точный город, например Москва"),
    category: EventCategory | None = Query(None, description="Категория события"),
    date_from: datetime | None = Query(None, description="События начиная с даты (UTC, формат ГГГГ-ММ-ДД)"),
    date_to: datetime | None = Query(None, description="События до даты (UTC, формат ГГГГ-ММ-ДД)"),
    available_only: bool = Query(False, description="Только события со свободными местами"),
    page: int = Query(1, ge=1, description="Номер страницы"),
    size: int = Query(settings.DEFAULT_PAGE_SIZE, ge=1, le=settings.MAX_PAGE_SIZE),
    db: Session = Depends(get_db),
) -> Page[EventOut]:
    category_value = category.value if category else None
    events, taken, total = events_service.list_events(
        db,
        q=q,
        city=city,
        category=category_value,
        date_from=date_from,
        date_to=date_to,
        available_only=available_only,
        page=page,
        size=size,
    )
    items = [events_service.build_event_out(event, taken.get(event.id, 0)) for event in events]
    return Page(
        items=items,
        total=total,
        page=page,
        size=size,
        pages=(total + size - 1) // size,
    )


@router.get("/categories", response_model=list[str], summary="Список категорий")
def categories() -> list[str]:
    return [c.value for c in EventCategory]


@router.get("/cities", response_model=list[str], summary="Города с мероприятиями")
def cities(db: Session = Depends(get_db)) -> list[str]:
    return events_service.list_cities(db)


@router.get("/{event_id}", response_model=EventOut, summary="Карточка мероприятия")
def get_event(event_id: int, db: Session = Depends(get_db)) -> EventOut:
    event = db.get(Event, event_id)
    if event is None or not event.is_published:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Мероприятие не найдено")
    taken = events_service.taken_map(db, [event.id]).get(event.id, 0)
    return events_service.build_event_out(event, taken)
