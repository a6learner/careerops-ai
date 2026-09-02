from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class RegisterUserRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        local_part, separator, domain = normalized.partition("@")
        if not local_part or separator == "" or "." not in domain:
            raise ValueError("email must be a valid email address")
        return normalized


class RegisteredUserResponse(BaseModel):
    id: UUID
    email: str
    created_at: datetime
