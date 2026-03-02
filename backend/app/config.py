import logging

from pydantic import model_validator
from pydantic_settings import BaseSettings
from functools import lru_cache

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://vpnpanel:changeme@postgres:5432/vpnpanel"
    REDIS_URL: str = "redis://redis:6379/0"
    SECRET_KEY: str = "changeme"
    ENCRYPTION_KEY: str = ""
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "admin"
    SSH_KEYS_DIR: str = "/app/ssh_keys"
    HEALTH_CHECK_INTERVAL: int = 60
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120  # 2 hours
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    @model_validator(mode="after")
    def _validate_security_defaults(self) -> "Settings":
        if self.SECRET_KEY == "changeme":
            raise ValueError("SECRET_KEY must be changed from default 'changeme'")
        if not self.ENCRYPTION_KEY:
            raise ValueError("ENCRYPTION_KEY must not be empty")
        if self.ADMIN_PASSWORD == "admin":
            logger.warning("ADMIN_PASSWORD is still 'admin' — change it after first login")
        return self

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
