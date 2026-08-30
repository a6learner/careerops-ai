from enum import StrEnum

from pydantic import BaseModel


class ErrorCode(StrEnum):
    DEPENDENCY_UNAVAILABLE = "DEPENDENCY_UNAVAILABLE"


class ErrorDetail(BaseModel):
    code: ErrorCode
    message: str
    request_id: str


class ErrorResponse(BaseModel):
    error: ErrorDetail
