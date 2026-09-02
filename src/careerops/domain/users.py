from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class UserAccount:
    id: UUID
    email: str
    created_at: datetime
