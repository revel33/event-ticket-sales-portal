from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models import Booking, BookingStatus, Event, User, UserRole
from app.schemas import EventCreate, EventUpdate, StatsOut
from app.services import bookings as bookings_service
from app.services import events as events_service
from app.services import stats as stats_service
from app.webui import (
    STATUS_TITLES,
    current_user,
    humanize_validation,
    redirect,
    render,
)

router = APIRouter(prefix="/admin", include_in_schema=False)

PAGE_SIZE = 20


def _require_admin(request: Request, db: Session) -> tuple[User | None, RedirectResponse | None]:
    user = current_user(request, db)
    if user is None:
        return None, redirect("/login", err="Сначала войдите в аккаунт")
    if user.role != UserRole.admin.value:
        return None, redirect("/", err="Раздел доступен только администраторам")
    return user, None


@router.get("", response_class=HTMLResponse, response_model=None)
def dashboard(request: Request, db: Session = Depends(get_db)) -> HTMLResponse | RedirectResponse:
    _, denial = _require_admin(request, db)
    if denial:
        return denial

    stats = StatsOut(**stats_service.collect_stats(db))
    status_rows = [
        (code, STATUS_TITLES[code], stats.bookings_by_status.get(code, 0))
        for code in ("booked", "confirmed", "cancelled", "expired")
    ]
    return render(request, db, "admin/dashboard.html", stats=stats, status_rows=status_rows)


@router.get("/events", response_class=HTMLResponse, response_model=None)
def events_list(
    request: Request,
    page: int = 1,
    db: Session = Depends(get_db),
) -> HTMLResponse | RedirectResponse:
    _, denial = _require_admin(request, db)
    if denial:
        return denial
    if page < 1:
        page = 1

    events, taken, total = events_service.list_events(
        db, include_all=True, page=page, size=PAGE_SIZE
    )
    items = [events_service.build_event_out(event, taken.get(event.id, 0)) for event in events]
    pages = (total + PAGE_SIZE - 1) // PAGE_SIZE

    return render(
        request,
        db,
        "admin/events.html",
        events=items,
        total=total,
        page=page,
        pages=pages,
        prev_url=f"/admin/events?page={page - 1}" if page > 1 else None,
        next_url=f"/admin/events?page={page + 1}" if page < pages else None,
    )


@router.get("/events/new", response_class=HTMLResponse, response_model=None)
def new_event_form(request: Request, db: Session = Depends(get_db)) -> HTMLResponse | RedirectResponse:
    _, denial = _require_admin(request, db)
    if denial:
        return denial
    return render(request, db, "admin/event_form.html", is_edit=False,
                  action_url="/admin/events/new", form={"is_published": "on"})


def _event_form_dict(**raw: str) -> dict:
    return {
        "title": raw["title"],
        "description": raw["description"],
        "category": raw["category"],
        "venue": raw["venue"],
        "city": raw["city"],
        "starts_at": raw["starts_at"],
        "price": raw["price"],
        "capacity": raw["capacity"],
        "image_url": raw["image_url"],
        "is_published": "on" if raw["is_published"] else "",
    }


@router.post("/events/new", response_model=None)
def create_event(
    request: Request,
    db: Session = Depends(get_db),
    title: str = Form(""),
    description: str = Form(""),
    category: str = Form(""),
    venue: str = Form(""),
    city: str = Form(""),
    starts_at: str = Form(""),
    price: str = Form(""),
    capacity: str = Form(""),
    image_url: str = Form(""),
    is_published: str = Form(""),
) -> HTMLResponse | RedirectResponse:
    _, denial = _require_admin(request, db)
    if denial:
        return denial

    form = _event_form_dict(
        title=title, description=description, category=category, venue=venue,
        city=city, starts_at=starts_at, price=price, capacity=capacity,
        image_url=image_url, is_published=is_published,
    )

    errors = None
    try:
        data = EventCreate(
            title=title,
            description=description,
            category=category,
            venue=venue,
            city=city,
            starts_at=starts_at or None,
            price=int(price or 0),
            capacity=int(capacity or 0),
            image_url=image_url,
        )
    except ValidationError as error:
        errors = humanize_validation(error)
    except ValueError:
        errors = ["Цена и количество мест должны быть целыми числами"]

    if errors:
        return render(request, db, "admin/event_form.html", is_edit=False,
                       action_url="/admin/events/new", form=form, errors=errors)

    try:
        events_service.create_event(db, data)
    except HTTPException as exc:
        return render(request, db, "admin/event_form.html", is_edit=False,
                      action_url="/admin/events/new", form=form, errors=[exc.detail])

    return redirect("/admin/events", msg="Мероприятие создано")


@router.get("/events/{event_id}/edit", response_class=HTMLResponse, response_model=None)
def edit_event_form(
    request: Request,
    event_id: int,
    db: Session = Depends(get_db),
) -> HTMLResponse | RedirectResponse:
    _, denial = _require_admin(request, db)
    if denial:
        return denial

    event = db.get(Event, event_id)
    if event is None:
        return render(request, db, "error.html", code=404,
                      text="Мероприятие не найдено", status_code=404)

    form = {
        "title": event.title,
        "description": event.description or "",
        "category": event.category,
        "venue": event.venue or "",
        "city": event.city,
        "starts_at": event.starts_at.strftime("%Y-%m-%dT%H:%M"),
        "price": str(event.price),
        "capacity": str(event.capacity),
        "image_url": event.image_url or "",
        "is_published": "on" if event.is_published else "",
    }
    return render(request, db, "admin/event_form.html", is_edit=True,
                  action_url=f"/admin/events/{event_id}/edit", form=form)


@router.post("/events/{event_id}/edit", response_model=None)
def update_event(
    request: Request,
    event_id: int,
    db: Session = Depends(get_db),
    title: str = Form(""),
    description: str = Form(""),
    category: str = Form(""),
    venue: str = Form(""),
    city: str = Form(""),
    starts_at: str = Form(""),
    price: str = Form(""),
    capacity: str = Form(""),
    image_url: str = Form(""),
    is_published: str = Form(""),
) -> HTMLResponse | RedirectResponse:
    _, denial = _require_admin(request, db)
    if denial:
        return denial

    form = _event_form_dict(
        title=title, description=description, category=category, venue=venue,
        city=city, starts_at=starts_at, price=price, capacity=capacity,
        image_url=image_url, is_published=is_published,
    )

    errors = None
    try:
        changes = EventUpdate(
            title=title or None,
            description=description,
            category=category or None,
            venue=venue,
            city=city,
            starts_at=starts_at or None,
            price=int(price) if price != "" else None,
            capacity=int(capacity) if capacity != "" else None,
            image_url=image_url,
            is_published=bool(is_published),
        ).model_dump(exclude_unset=True)
    except ValidationError as error:
        errors = humanize_validation(error)
    except ValueError:
        errors = ["Цена и количество мест должны быть целыми числами"]

    if errors:
        return render(request, db, "admin/event_form.html", is_edit=True,
                       action_url=f"/admin/events/{event_id}/edit", form=form, errors=errors)

    try:
        events_service.update_event(db, event_id, changes)
    except HTTPException as exc:
        return render(request, db, "admin/event_form.html", is_edit=True,
                      action_url=f"/admin/events/{event_id}/edit", form=form, errors=[exc.detail])

    return redirect("/admin/events", msg=f"Мероприятие #{event_id} обновлено")


@router.post("/events/{event_id}/delete")
def delete_event(request: Request, event_id: int, db: Session = Depends(get_db)) -> RedirectResponse:
    _, denial = _require_admin(request, db)
    if denial:
        return denial

    try:
        events_service.delete_event(db, event_id)
    except HTTPException as exc:
        return redirect("/admin/events", err=exc.detail)

    return redirect("/admin/events", msg=f"Мероприятие #{event_id} удалено")


@router.get("/bookings", response_class=HTMLResponse, response_model=None)
def all_bookings(
    request: Request,
    status: str | None = None,
    page: int = 1,
    db: Session = Depends(get_db),
) -> HTMLResponse | RedirectResponse:
    _, denial = _require_admin(request, db)
    if denial:
        return denial
    if page < 1:
        page = 1
    if status not in STATUS_TITLES:
        status = None

    bookings_service.sweep_expired_bookings(db)

    base = select(Booking)
    if status:
        base = base.where(Booking.status == status)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    bookings = (
        db.scalars(
            base.options(
                selectinload(Booking.event),
                selectinload(Booking.user),
                selectinload(Booking.tickets),
            )
            .order_by(Booking.id.desc())
            .offset((page - 1) * PAGE_SIZE)
            .limit(PAGE_SIZE)
        )
        .all()
    )
    pages = (total + PAGE_SIZE - 1) // PAGE_SIZE
    status_options = [(code, STATUS_TITLES[code]) for code in STATUS_TITLES]

    suffix = f"&status={status}" if status else ""
    return render(
        request,
        db,
        "admin/bookings.html",
        bookings=bookings,
        total=total,
        page=page,
        pages=pages,
        status=status,
        status_options=status_options,
        prev_url=f"/admin/bookings?page={page - 1}{suffix}" if page > 1 else None,
        next_url=f"/admin/bookings?page={page + 1}{suffix}" if page < pages else None,
    )
