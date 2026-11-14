from datetime import datetime, timedelta, timezone
from enum import Enum

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config import settings
from app.database import Base


class UserRole(str, Enum):

    user = "user"
    admin = "admin"


class EventCategory(str, Enum):

    concert = "концерт"
    theater = "театр"
    sport = "спорт"
    festival = "фестиваль"
    exhibition = "выставка"
    lecture = "лекция"


class BookingStatus(str, Enum):

    booked = "booked"
    confirmed = "confirmed"
    cancelled = "cancelled"
    expired = "expired"


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def booking_deadline() -> datetime:
    return utcnow() + timedelta(minutes=settings.BOOKING_TTL_MINUTES)


class User(Base):

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(255), default="")
    role: Mapped[str] = mapped_column(String(20), default=UserRole.user.value)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    bookings: Mapped[list["Booking"]] = relationship(back_populates="user")


class Event(Base):

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(30), index=True)
    venue: Mapped[str] = mapped_column(String(200), default="")
    city: Mapped[str] = mapped_column(String(100), index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    price: Mapped[int] = mapped_column(Integer, default=0)
    capacity: Mapped[int] = mapped_column(Integer, default=0)
    image_url: Mapped[str] = mapped_column(String(500), default="")
    is_published: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    bookings: Mapped[list["Booking"]] = relationship(back_populates="event")


class Booking(Base):

    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    price_per_ticket: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default=BookingStatus.booked.value, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime, default=booking_deadline)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped["User"] = relationship(back_populates="bookings")
    event: Mapped["Event"] = relationship(back_populates="bookings")
    tickets: Mapped[list["Ticket"]] = relationship(back_populates="booking")

    @property
    def total_price(self) -> int:
        return self.quantity * self.price_per_ticket


class Ticket(Base):

    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(primary_key=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey("bookings.id", ondelete="CASCADE"), index=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True)

    booking: Mapped["Booking"] = relationship(back_populates="tickets")
    event: Mapped["Event"] = relationship()
    user: Mapped["User"] = relationship()
