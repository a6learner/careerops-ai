from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CAREEROPS_", env_file=".env", extra="ignore")

    environment: str = Field(default="local", alias="CAREEROPS_ENV")
    service_name: str = "careerops-api"
    database_url: str = "postgresql+asyncpg://careerops:careerops@localhost:5432/careerops"
    redis_url: str = "redis://localhost:6379/0"
    log_level: str = "INFO"
    jwt_secret: str = "change-me-in-local-development-secret-32-bytes-minimum"
    access_token_expire_minutes: int = 30


@lru_cache
def get_settings() -> Settings:
    return Settings()
