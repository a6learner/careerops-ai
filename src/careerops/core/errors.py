from enum import StrEnum

from pydantic import BaseModel


class ErrorCode(StrEnum):
    DEPENDENCY_UNAVAILABLE = "DEPENDENCY_UNAVAILABLE"
    EMAIL_ALREADY_REGISTERED = "EMAIL_ALREADY_REGISTERED"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"


class ErrorDetail(BaseModel):
    code: ErrorCode
    message: str
    request_id: str


class ErrorResponse(BaseModel):
    error: ErrorDetail
