from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError
from sqlalchemy import desc, select
from sqlalchemy.orm import Session, selectinload

from app.config import settings
from app.database import get_db
from app.models import Booking, Event, Ticket, User, utcnow
from app.schemas import UserCreate
from app.security import create_access_token
from app.services import bookings as bookings_service
from app.services import events as events_service
from app.services import users as users_service
from app.webui import (
    CATEGORIES,
    current_user,
    humanize_validation,
    parse_date,
    redirect,
    render,
)

router = APIRouter(include_in_schema=False)

PAGE_SIZE = 9


def _page_url(params: dict, page_number: int) -> str:
    clean = {key: value for key, value in params.items() if value}
    clean["page"] = page_number
    return f"/?{urlencode(clean)}"


def _login_response(user: User, message: str) -> RedirectResponse:
    response = redirect("/cabinet", msg=message)
    response.set_cookie(
        "access_token",
        create_access_token(user),
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        httponly=True,
        samesite="lax",
    )
    return response


@router.get("/", response_class=HTMLResponse)
def catalog(
    request: Request,
    q: str | None = None,
    city: str | None = None,
    category: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    available_only: str | None = None,
    page: int = 1,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    if page < 1:
        page = 1

    error = None
    parsed_from = parsed_to = None
    try:
        parsed_from = parse_date(date_from)
        parsed_to = parse_date(date_to)
    except ValueError:
        error = "Неверный формат даты — используйте ГГГГ-ММ-ДД"

    category_value = category if category in CATEGORIES else None

    events, taken, total = events_service.list_events(
        db,
        q=q,
        city=city,
        category=category_value,
        date_from=parsed_from,
        date_to=parsed_to,
        available_only=bool(available_only),
        page=page,
        size=PAGE_SIZE,
    )
    pages = (total + PAGE_SIZE - 1) // PAGE_SIZE
    items = [events_service.build_event_out(e, taken.get(e.id, 0)) for e in events]

    params = {
        "q": q,
        "city": city,
        "category": category,
        "date_from": date_from,
        "date_to": date_to,
        "available_only": "on" if available_only else "",
    }
    return render(
        request,
        db,
        "index.html",
        events=items,
        total=total,
        page=page,
        pages=pages,
        cities=events_service.list_cities(db),
        q=q,
        city=city,
        category=category,
        date_from=date_from,
        date_to=date_to,
        available_only=available_only,
        prev_url=_page_url(params, page - 1) if page > 1 else None,
        next_url=_page_url(params, page + 1) if page < pages else None,
        err=error or request.query_params.get("err"),
    )


@router.get("/events/{event_id}", response_class=HTMLResponse)
def event_page(request: Request, event_id: int, db: Session = Depends(get_db)) -> HTMLResponse:
    event = db.get(Event, event_id)
    if event is None or not event.is_published:
        return render(
            request,
            db,
            "error.html",
            code=404,
            text="Мероприятие не найдено или снято с продажи",
            status_code=404,
        )

    taken = events_service.taken_map(db, [event.id]).get(event.id, 0)
    event_out = events_service.build_event_out(event, taken)
    can_buy = event_out.available > 0 and event.starts_at > utcnow()

    return render(
        request,
        db,
        "event.html",
        event=event_out,
        can_buy=can_buy,
        ttl=settings.BOOKING_TTL_MINUTES,
    )


@router.get("/login", response_class=HTMLResponse, response_model=None)
def login_page(request: Request, db: Session = Depends(get_db)) -> HTMLResponse | RedirectResponse:
    if request.cookies.get("access_token") and current_user(request, db):
        return redirect("/cabinet")
    return render(request, db, "login.html")


@router.post("/login", response_model=None)
def login_post(
    request: Request,
    db: Session = Depends(get_db),
    email: str = Form(""),
    password: str = Form(""),
) -> HTMLResponse | RedirectResponse:
    try:
        user = users_service.authenticate(db, email, password)
    except HTTPException:
        return render(request, db, "login.html", email=email, err="Неверный email или пароль")
    return _login_response(user, "Вы вошли в личный кабинет")


@router.get("/register", response_class=HTMLResponse, response_model=None)
def register_page(request: Request, db: Session = Depends(get_db)) -> HTMLResponse | RedirectResponse:
    if request.cookies.get("access_token") and current_user(request, db):
        return redirect("/cabinet")
    return render(request, db, "register.html", form={})


@router.post("/register", response_model=None)
def register_post(
    request: Request,
    db: Session = Depends(get_db),
    email: str = Form(""),
    full_name: str = Form(""),
    password: str = Form(""),
) -> HTMLResponse | RedirectResponse:
    form = {"email": email, "full_name": full_name, "password": password}
    try:
        data = UserCreate(email=email, full_name=full_name, password=password)
    except ValidationError as error:
        return render(request, db, "register.html", form=form, errors=humanize_validation(error))

    if users_service.get_by_email(db, data.email) is not None:
        return render(request, db, "register.html", form=form, errors=["Этот email уже зарегистрирован"])

    user = users_service.create_user(db, email=data.email, password=password, full_name=data.full_name)
    return _login_response(user, "Аккаунт создан — добро пожаловать!")


@router.post("/logout")
def logout() -> RedirectResponse:
    response = redirect("/", msg="Вы вышли из аккаунта")
    response.delete_cookie("access_token")
    return response


@router.get("/cabinet", response_class=HTMLResponse, response_model=None)
def cabinet_page(request: Request, db: Session = Depends(get_db)) -> HTMLResponse | RedirectResponse:
    user = current_user(request, db)
    if user is None:
        return redirect("/login", err="Сначала войдите в аккаунт")

    bookings_service.sweep_expired_bookings(db)

    bookings = (
        db.scalars(
            select(Booking)
            .options(selectinload(Booking.event), selectinload(Booking.tickets))
            .where(Booking.user_id == user.id)
            .order_by(desc(Booking.created_at))
        )
        .all()
    )
    tickets = (
        db.scalars(
            select(Ticket)
            .options(selectinload(Ticket.event))
            .where(Ticket.user_id == user.id)
            .order_by(Ticket.id.desc())
        )
        .all()
    )
    return render(request, db, "cabinet.html", bookings=bookings, tickets=tickets)


@router.post("/bookings")
def create_booking(
    request: Request,
    db: Session = Depends(get_db),
    event_id: int = Form(...),
    quantity: str = Form("1"),
) -> RedirectResponse:
    user = current_user(request, db)
    if user is None:
        return redirect("/login", err="Войдите, чтобы бронировать билеты")

    try:
        qty = int(quantity)
        if not 1 <= qty <= 10:
            raise ValueError
    except ValueError:
        return redirect(f"/events/{event_id}", err="Количество билетов — число от 1 до 10")

    try:
        booking = bookings_service.create_booking(db, user, event_id, qty)
    except HTTPException as exc:
        return redirect(f"/events/{event_id}", err=exc.detail)

    return redirect(
        "/cabinet",
        msg=f"Бронь #{booking.id} создана — подтвердите её в течение "
            f"{settings.BOOKING_TTL_MINUTES} минут",
    )


@router.post("/bookings/{booking_id}/confirm")
def confirm_booking(
    request: Request,
    booking_id: int,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    user = current_user(request, db)
    if user is None:
        return redirect("/login", err="Сначала войдите в аккаунт")

    try:
        booking = bookings_service.get_user_booking(db, user, booking_id)
        bookings_service.confirm_booking(db, booking)
    except HTTPException as exc:
        return redirect("/cabinet", err=exc.detail)

    return redirect("/cabinet", msg=f"Бронь #{booking_id} подтверждена — билеты выданы ниже")


@router.post("/bookings/{booking_id}/cancel")
def cancel_booking(
    request: Request,
    booking_id: int,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    user = current_user(request, db)
    if user is None:
        return redirect("/login", err="Сначала войдите в аккаунт")

    try:
        booking = bookings_service.get_user_booking(db, user, booking_id)
        bookings_service.cancel_booking(db, booking)
    except HTTPException as exc:
        return redirect("/cabinet", err=exc.detail)

    return redirect("/cabinet", msg=f"Бронь #{booking_id} отменена, места возвращены в продажу")
