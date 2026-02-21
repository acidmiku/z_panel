from pydantic_settings import BaseSettings
from functools import lru_cache


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

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
