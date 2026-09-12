from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CAREEROPS_", env_file=".env", extra="ignore")

    environment: str = Field(default="local", alias="CAREEROPS_ENV")
    service_name: str = "careerops-api"
    database_url: str = "postgresql+asyncpg://careerops:careerops@localhost:5432/careerops"
    redis_url: str = "redis://localhost:6379/0"
    parse_run_stale_after_seconds: int = Field(default=300, ge=30)
    parse_run_recovery_batch_size: int = Field(default=100, ge=1, le=1_000)
    analysis_run_stale_after_seconds: int = Field(default=300, ge=30)
    analysis_run_recovery_batch_size: int = Field(default=100, ge=1, le=1_000)
    llm_provider: Literal["fake", "groq"] = "fake"
    llm_model: str = "openai/gpt-oss-20b"
    llm_base_url: str = "https://api.groq.com/openai/v1"
    llm_api_key: SecretStr | None = None
    llm_timeout_seconds: float = Field(default=30.0, ge=1.0, le=120.0)
    llm_max_attempts: int = Field(default=2, ge=1, le=3)
    llm_retry_base_delay_seconds: float = Field(default=0.25, ge=0.0, le=5.0)
    llm_max_output_tokens: int = Field(default=1_500, ge=100, le=4_000)
    log_level: str = "INFO"
    jwt_secret: str = "change-me-in-local-development-secret-32-bytes-minimum"
    access_token_expire_minutes: int = 30


@lru_cache
def get_settings() -> Settings:
    return Settings()
