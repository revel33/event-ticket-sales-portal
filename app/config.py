import os


def _database_url() -> str:
    env_url = os.getenv("DATABASE_URL", "")
    if "://" in env_url:
        return env_url
    return "sqlite:///./tickets.db"


class Settings:

    DATABASE_URL: str = _database_url()

    SECRET_KEY: str = os.getenv("SECRET_KEY", "study-project-secret-key-change-me")

    ALGORITHM: str = "HS256"

    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))

    BOOKING_TTL_MINUTES: int = int(os.getenv("BOOKING_TTL_MINUTES", "15"))

    DEFAULT_PAGE_SIZE: int = 10
    MAX_PAGE_SIZE: int = 50

    EXPIRE_SWEEP_INTERVAL_SECONDS: int = 60


settings = Settings()
