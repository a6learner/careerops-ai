from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class UserAccount:
    id: UUID
    email: str
    created_at: datetime


@dataclass(frozen=True)
class UserCredentials:
    id: UUID
    email: str
    password_hash: str
