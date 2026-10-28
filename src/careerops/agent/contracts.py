from pathlib import Path
from typing import Literal, Self
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator

from careerops.domain.project_records import CheckpointInput, CheckpointRecord


class AgentError(Exception):
    def __init__(self, code: str, message: str, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


class AgentConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    api_url: str = "http://127.0.0.1:8000"
    state_dir: Path

    @model_validator(mode="after")
    def local_origin_only(self) -> Self:
        try:
            url = urlsplit(self.api_url)
            port = url.port
        except ValueError as exc:
            raise ValueError("Invalid local API origin.") from exc
        if (
            url.scheme != "http"
            or url.hostname not in {"127.0.0.1", "localhost", "::1"}
            or url.username is not None
            or url.password is not None
            or url.path not in {"", "/"}
            or url.query
            or url.fragment
            or (port is not None and port < 1)
        ):
            raise ValueError("The first agent client accepts only an explicit local HTTP origin.")
        return self


class AgentCredentials(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    api_url: str
    user_id: UUID
    access_token: SecretStr


class PendingCheckpoint(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    packet_id: UUID
    api_url: str
    user_id: UUID
    project_id: UUID
    idempotency_key: UUID
    payload: CheckpointInput
    content_sha256: str = Field(pattern="^[0-9a-f]{64}$")


class SubmissionResult(BaseModel):
    packet_id: UUID
    state: Literal["pending", "accepted", "rejected"]
    record: CheckpointRecord | None = None
    error_code: str | None = None
    message: str


class PendingSummary(BaseModel):
    packet_id: UUID
    project_id: UUID
    title: str
    state: Literal["pending", "rejected"]
    error_code: str | None = None


class PendingPage(BaseModel):
    items: list[PendingSummary]
    has_more: bool


class RecordQuery(BaseModel):
    query: str | None = Field(default=None, min_length=1, max_length=100)
    cursor: str | None = Field(default=None, max_length=512)
    limit: int = Field(default=20, ge=1, le=100)
