from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models import EventCategory

ModelT = TypeVar("ModelT")


class Page(BaseModel, Generic[ModelT]):

    items: list[ModelT]
    total: int
    page: int
    size: int
    pages: int


class UserCreate(BaseModel):

    email: EmailStr
    full_name: str = Field(min_length=1, max_length=255, description="Имя и фамилия")
    password: str = Field(min_length=6, max_length=72, description="Минимум 6 символов")


class UserOut(BaseModel):

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str
    role: str = Field(description="user или admin")
    created_at: datetime


class TokenOut(BaseModel):

    access_token: str
    token_type: str = "bearer"


class EventCreate(BaseModel):

    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    category: EventCategory
    venue: str = Field(default="", max_length=200, description="Место проведения")
    city: str = Field(min_length=1, max_length=100)
    starts_at: datetime = Field(description="Дата и время начала (UTC)")
    price: int = Field(ge=0, description="Цена билета в рублях (0 — бесплатно)")
    capacity: int = Field(gt=0, description="Общее количество мест")
    image_url: str = ""


class EventUpdate(BaseModel):

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    category: EventCategory | None = None
    venue: str | None = Field(default=None, max_length=200)
    city: str | None = Field(default=None, min_length=1, max_length=100)
    starts_at: datetime | None = None
    price: int | None = Field(default=None, ge=0)
    capacity: int | None = Field(default=None, gt=0)
    image_url: str | None = None
    is_published: bool | None = Field(default=None, description="Видно ли в каталоге")


class EventShort(BaseModel):

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    starts_at: datetime
    venue: str
    city: str
    price: int
    image_url: str


class EventOut(EventShort):

    model_config = ConfigDict(from_attributes=True)

    description: str
    category: str
    capacity: int
    is_published: bool
    created_at: datetime
    available: int = Field(default=0, description="Свободных мест прямо сейчас")


class BookingCreate(BaseModel):

    event_id: int
    quantity: int = Field(default=1, ge=1, le=10, description="За раз можно взять до 10 билетов")


class TicketShort(BaseModel):

    model_config = ConfigDict(from_attributes=True)

    code: str


class BookingOut(BaseModel):

    model_config = ConfigDict(from_attributes=True)

    id: int
    quantity: int
    price_per_ticket: int
    total_price: int = Field(description="Итоговая стоимость, руб.")
    status: str = Field(description="booked | confirmed | cancelled | expired")
    created_at: datetime
    expires_at: datetime | None = Field(description="До какого момента удерживаются места")
    confirmed_at: datetime | None = None
    event: EventShort
    user_id: int
    tickets: list[TicketShort] = []


class TicketOut(BaseModel):

    model_config = ConfigDict(from_attributes=True)

    code: str
    event: EventShort
    booking_id: int


class EventSalesOut(BaseModel):

    event_id: int
    title: str
    tickets_sold: int
    revenue: int


class StatsOut(BaseModel):

    total_users: int
    total_events: int
    bookings_by_status: dict[str, int]
    tickets_sold: int
    revenue: int
    top_events: list[EventSalesOut]
