from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_LOCAL_JWT_SECRET = "change-me-in-local-development-secret-32-bytes-minimum"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CAREEROPS_", env_file=".env", extra="ignore")

    environment: str = Field(default="local", alias="CAREEROPS_ENV")
    service_name: str = "careerops-api"
    database_url: str = "postgresql+asyncpg://careerops:careerops@localhost:5432/careerops"
    redis_url: str = "redis://localhost:6379/0"
    dashboard_cache_ttl_seconds: int = Field(default=30, ge=1, le=3_600)
    redis_socket_timeout_seconds: float = Field(default=0.2, gt=0.0, le=5.0)
    parse_run_stale_after_seconds: int = Field(default=300, ge=30)
    parse_run_recovery_batch_size: int = Field(default=100, ge=1, le=1_000)
    analysis_run_stale_after_seconds: int = Field(default=300, ge=30)
    analysis_run_recovery_batch_size: int = Field(default=100, ge=1, le=1_000)
    analysis_rate_limit: int = Field(default=5, ge=1, le=1_000)
    analysis_rate_limit_window_seconds: int = Field(default=3_600, ge=1, le=86_400)
    embedding_run_stale_after_seconds: int = Field(default=300, ge=30)
    embedding_run_recovery_batch_size: int = Field(default=100, ge=1, le=1_000)
    embedding_provider: Literal["fake", "gemini"] = "fake"
    gemini_api_key: SecretStr | None = None
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    embedding_timeout_seconds: float = Field(default=30.0, ge=1.0, le=120.0)
    embedding_max_attempts: int = Field(default=2, ge=1, le=3)
    embedding_retry_base_delay_seconds: float = Field(default=0.25, ge=0.0, le=5.0)
    llm_provider: Literal["fake", "groq"] = "fake"
    llm_model: str = "openai/gpt-oss-20b"
    llm_base_url: str = "https://api.groq.com/openai/v1"
    llm_api_key: SecretStr | None = None
    llm_timeout_seconds: float = Field(default=30.0, ge=1.0, le=120.0)
    llm_max_attempts: int = Field(default=2, ge=1, le=3)
    llm_retry_base_delay_seconds: float = Field(default=0.25, ge=0.0, le=5.0)
    llm_max_output_tokens: int = Field(default=1_500, ge=100, le=4_000)
    evidence_matcher_provider: Literal["fake", "groq"] = "fake"
    log_level: str = "INFO"
    jwt_secret: str = DEFAULT_LOCAL_JWT_SECRET
    access_token_expire_minutes: int = 30

    @model_validator(mode="after")
    def reject_unsafe_production_defaults(self) -> "Settings":
        if self.environment.casefold() == "production" and (
            self.jwt_secret == DEFAULT_LOCAL_JWT_SECRET
        ):
            raise ValueError("production requires an explicit CAREEROPS_JWT_SECRET")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
