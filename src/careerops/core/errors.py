from enum import StrEnum

from pydantic import BaseModel


class ErrorCode(StrEnum):
    DEPENDENCY_UNAVAILABLE = "DEPENDENCY_UNAVAILABLE"
    EMAIL_ALREADY_REGISTERED = "EMAIL_ALREADY_REGISTERED"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    TOKEN_INVALID = "TOKEN_INVALID"
    TOKEN_MISSING = "TOKEN_MISSING"


class ErrorDetail(BaseModel):
    code: ErrorCode
    message: str
    request_id: str


class ErrorResponse(BaseModel):
    error: ErrorDetail
