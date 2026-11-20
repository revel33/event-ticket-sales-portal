import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.routers import admin, auth, bookings, events, tickets, web, web_admin
from app.seed import seed_if_empty
from app.services.bookings import sweep_expired_bookings

BASE_DIR = Path(__file__).resolve().parent


async def expire_bookings_loop() -> None:
    while True:
        await asyncio.sleep(settings.EXPIRE_SWEEP_INTERVAL_SECONDS)
        db = SessionLocal()
        try:
            sweep_expired_bookings(db)
        finally:
            db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        seed_if_empty(db)

    task = asyncio.create_task(expire_bookings_loop())
    try:
        yield
    finally:
        task.cancel()


app = FastAPI(
    title="Портал продажи билетов на мероприятия",
    description=(
        "Учебный проект на FastAPI: каталог мероприятий, бронирование "
        "с удержанием мест на 15 минут, подтверждение брони с выдачей "
        "электронных билетов, роли пользователя и администратора.\n\n"
        "**REST API:** получите токен через `POST /api/auth/token` "
        "(email указывается в поле `username`) и нажмите кнопку "
        "**Authorize**.\n\n"
        "**Веб-интерфейс (Jinja2):** главная страница `http://127.0.0.1:8000/` "
        "— каталог событий, личный кабинет и админ-панель."
    ),
    version="1.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

app.include_router(auth.router)
app.include_router(events.router)
app.include_router(bookings.router)
app.include_router(tickets.router)
app.include_router(admin.router)

app.include_router(web.router)
app.include_router(web_admin.router)
