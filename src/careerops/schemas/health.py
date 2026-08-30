from typing import Literal

from pydantic import BaseModel


class HealthCheck(BaseModel):
    status: Literal["ok"]
    service: str


class ReadinessCheck(BaseModel):
    status: Literal["ready", "not_ready"]
    database: bool
