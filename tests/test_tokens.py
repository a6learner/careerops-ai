from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest

from careerops.domain.errors import ExpiredTokenError, InvalidTokenError
from careerops.security.tokens import TokenIssuer, TokenVerifier


def test_token_issuer_creates_signed_access_token_with_user_subject() -> None:
    user_id = uuid4()
    secret = "test-secret-with-at-least-32-bytes"
    issuer = TokenIssuer(secret=secret, expires_after=timedelta(minutes=30))

    token = issuer.issue_access_token(user_id)
    payload = jwt.decode(token.value, secret, algorithms=["HS256"])

    assert token.token_type == "bearer"
    assert payload["sub"] == str(user_id)
    assert "iat" in payload
    assert "exp" in payload


def test_access_token_rejects_wrong_secret() -> None:
    issuer = TokenIssuer(
        secret="test-secret-with-at-least-32-bytes",
        expires_after=timedelta(minutes=30),
    )

    token = issuer.issue_access_token(uuid4())

    with pytest.raises(jwt.InvalidTokenError):
        jwt.decode(token.value, "wrong-secret-with-at-least-32-bytes", algorithms=["HS256"])


def test_token_verifier_returns_user_id_from_valid_token() -> None:
    user_id = uuid4()
    secret = "test-secret-with-at-least-32-bytes"
    issuer = TokenIssuer(secret=secret, expires_after=timedelta(minutes=30))
    token = issuer.issue_access_token(user_id)

    verified_user_id = TokenVerifier(secret=secret).verify_access_token(token.value)

    assert verified_user_id == user_id


def test_token_verifier_rejects_expired_token() -> None:
    user_id = uuid4()
    secret = "test-secret-with-at-least-32-bytes"
    expired = jwt.encode(
        {
            "sub": str(user_id),
            "iat": datetime.now(UTC) - timedelta(hours=2),
            "exp": datetime.now(UTC) - timedelta(hours=1),
        },
        secret,
        algorithm="HS256",
    )

    with pytest.raises(ExpiredTokenError):
        TokenVerifier(secret=secret).verify_access_token(expired)


def test_token_verifier_rejects_missing_subject() -> None:
    secret = "test-secret-with-at-least-32-bytes"
    token = jwt.encode(
        {
            "iat": datetime.now(UTC),
            "exp": datetime.now(UTC) + timedelta(minutes=30),
        },
        secret,
        algorithm="HS256",
    )

    with pytest.raises(InvalidTokenError):
        TokenVerifier(secret=secret).verify_access_token(token)
