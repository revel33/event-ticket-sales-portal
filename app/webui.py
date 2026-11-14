from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode

from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.models import EventCategory, User
from app.security import decode_access_token

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))

CATEGORIES = [category.value for category in EventCategory]

STATUS_TITLES = {
    "booked": "Забронирована",
    "confirmed": "Подтверждена",
    "cancelled": "Отменена",
    "expired": "Истекла",
}

_MONTHS = (
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
)


def format_dt(value: datetime | None) -> str:
    if not value:
        return "—"
    return f"{value.day:02d} {_MONTHS[value.month - 1]} {value.year}, {value:%H:%M} UTC"


def format_money(value: int | None) -> str:
    if not value:
        return "Бесплатно"
    return f"{value:,}".replace(",", " ") + " ₽"


templates.env.filters["dt"] = format_dt
templates.env.filters["money"] = format_money


def current_user(request: Request, db: Session) -> User | None:
    token = request.cookies.get("access_token")
    if not token:
        return None
    try:
        payload = decode_access_token(token)
        user_id = int(payload["sub"])
    except (HTTPException, KeyError, ValueError):
        return None
    return db.get(User, user_id)


def render(
    request: Request,
    db: Session,
    template_name: str,
    status_code: int = 200,
    **context,
) -> HTMLResponse:
    context.setdefault("user", current_user(request, db))
    context.setdefault("categories", CATEGORIES)
    if "msg" not in context:
        context["msg"] = request.query_params.get("msg")
    if "err" not in context:
        context["err"] = request.query_params.get("err")
    return templates.TemplateResponse(request, template_name, context, status_code=status_code)


def redirect(url: str, **params) -> RedirectResponse:
    if params:
        clean = {key: value for key, value in params.items() if value}
        url = f"{url}?{urlencode(clean)}"
    return RedirectResponse(url, status_code=303)


def parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


_FIELD_TITLES = {
    "email": "Email",
    "full_name": "Имя",
    "password": "Пароль",
    "title": "Название",
    "description": "Описание",
    "category": "Категория",
    "venue": "Место проведения",
    "city": "Город",
    "starts_at": "Дата и время начала",
    "price": "Цена",
    "capacity": "Количество мест",
    "image_url": "Ссылка на изображение",
    "is_published": "Публикация",
}

_MESSAGE_TRANSLATIONS = (
    ("Field required", "обязательное поле"),
    ("String should have at least 6 characters", "минимум 6 символов"),
    ("String should have at most 72 characters", "максимум 72 символа"),
    ("String should have at least 1 character", "не может быть пустым"),
    ("value is not a valid email address", "некорректный email"),
    ("Input should be greater than 0", "должно быть больше нуля"),
    ("Input should be greater than or equal to 0", "не может быть отрицательным"),
    ("Input should be a valid datetime", "некорректная дата и время"),
    ("Input should be a valid integer", "ожидается целое число"),
    ("Input should be", "недопустимое значение"),
)


def _translate_error(message: str) -> str:
    for english, russian in _MESSAGE_TRANSLATIONS:
        if message.startswith(english):
            return russian
    return message


def humanize_validation(error: ValidationError) -> list[str]:
    result = []
    for item in error.errors():
        field = str(item["loc"][0]) if item["loc"] else "Форма"
        title = _FIELD_TITLES.get(field, field)
        result.append(f"{title}: {_translate_error(item['msg'])}")
    return result
