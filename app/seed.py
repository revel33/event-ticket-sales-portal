from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Event, EventCategory, User, UserRole, utcnow
from app.security import hash_password

_DEMO_EVENTS = [
    {
        "title": "Концерт группы «Ночные огни»",
        "category": EventCategory.concert.value,
        "venue": "Дворец спорта «Атлант»",
        "city": "Москва",
        "days_ahead": 7,
        "hour": 19,
        "price": 4500,
        "capacity": 3000,
        "description": "Большой вечерний концерт в поддержку нового альбома: световое шоу и два часа живого звука.",
    },
    {
        "title": "Спектакль «Вишнёвый сад»",
        "category": EventCategory.theater.value,
        "venue": "Театральная сцена «Ангажемент»",
        "city": "Санкт-Петербург",
        "days_ahead": 10,
        "hour": 19,
        "price": 2200,
        "capacity": 200,
        "description": "Классическая постановка Чехова в камерном зале на 200 мест.",
    },
    {
        "title": "Хоккей: «Ледовые львы» — «Северные волки»",
        "category": EventCategory.sport.value,
        "venue": "Дворец игровых видов спорта",
        "city": "Екатеринбург",
        "days_ahead": 5,
        "hour": 18,
        "price": 1500,
        "capacity": 8000,
        "description": "Домашний матч в рамках регулярного чемпионата.",
    },
    {
        "title": "Фестиваль уличной еды «Вкусный город»",
        "category": EventCategory.festival.value,
        "venue": "Парк «Сокольники»",
        "city": "Москва",
        "days_ahead": 21,
        "hour": 12,
        "price": 800,
        "capacity": 15000,
        "description": "Поле из фудкортов, мастер-классы от шефов и музыкальная сцена.",
    },
    {
        "title": "Выставка «Звёздное небо: путешествие к планетам»",
        "category": EventCategory.exhibition.value,
        "venue": "Планетарий №1",
        "city": "Санкт-Петербург",
        "days_ahead": 3,
        "hour": 10,
        "price": 600,
        "capacity": 500,
        "description": "Интерактивная выставка о Солнечной системе с проекциями купола планетария.",
    },
    {
        "title": "Лекция «Как работает искусственный интеллект»",
        "category": EventCategory.lecture.value,
        "venue": "Конгресс-холл «Техноград»",
        "city": "Екатеринбург",
        "days_ahead": 12,
        "hour": 19,
        "price": 900,
        "capacity": 150,
        "description": "Научпоп-лекция о машинном обучении: от простых моделей до больших языковых.",
    },
    {
        "title": "Стендап-концерт «Смех без правил»",
        "category": EventCategory.concert.value,
        "venue": "Клуб «Панорама»",
        "city": "Москва",
        "days_ahead": 9,
        "hour": 20,
        "price": 1800,
        "capacity": 400,
        "description": "Смешанная программа: пять комиков и один микрофон.",
    },
    {
        "title": "Фестиваль света «Город огней»",
        "category": EventCategory.festival.value,
        "venue": "Набережная Городского пруда",
        "city": "Екатеринбург",
        "days_ahead": 16,
        "hour": 21,
        "price": 0,
        "capacity": 20000,
        "description": "Световые инсталляции вдоль набережной, финальный лазерный спектакль в 23:00.",
    },
]


def seed_if_empty(db: Session) -> None:
    users_count = db.scalar(select(func.count(User.id)))
    if users_count:
        return

    db.add_all(
        [
            User(
                email="admin@example.com",
                hashed_password=hash_password("admin123"),
                full_name="Администратор портала",
                role=UserRole.admin.value,
            ),
            User(
                email="user@example.com",
                hashed_password=hash_password("user123"),
                full_name="Иван Иванов",
                role=UserRole.user.value,
            ),
        ]
    )

    now = utcnow()
    for item in _DEMO_EVENTS:
        starts_at = (now + timedelta(days=item["days_ahead"])).replace(
            hour=item["hour"], minute=0, second=0, microsecond=0
        )
        db.add(
            Event(
                title=item["title"],
                description=item["description"],
                category=item["category"],
                venue=item["venue"],
                city=item["city"],
                starts_at=starts_at,
                price=item["price"],
                capacity=item["capacity"],
                is_published=True,
            )
        )

    db.commit()
