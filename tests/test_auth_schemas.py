import pytest
from pydantic import ValidationError

from careerops.schemas.auth import RegisterUserRequest


def test_register_request_normalizes_email() -> None:
    payload = RegisterUserRequest(email=" Student@Example.COM ", password="strong-password")

    assert payload.email == "student@example.com"


def test_register_request_rejects_short_password() -> None:
    with pytest.raises(ValidationError):
        RegisterUserRequest(email="student@example.com", password="short")


def test_register_request_rejects_invalid_email_shape() -> None:
    with pytest.raises(ValidationError):
        RegisterUserRequest(email="not-an-email", password="strong-password")
