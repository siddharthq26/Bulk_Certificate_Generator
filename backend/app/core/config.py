from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Bulk Certificate Generator"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://certuser:certpass@localhost:5432/certdb"
    SYNC_DATABASE_URL: str = "postgresql://certuser:certpass@localhost:5432/certdb"

    # Redis / Celery
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    # Certificate storage
    CERT_STORAGE_PATH: str = "./certificates"

    # Security
    SECRET_KEY: str = "change-me-in-production"

    # Optional Email / SMTP Delivery
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = "certificates@certifyhub.com"

    model_config = ConfigDict(env_file=".env", extra="ignore")


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

