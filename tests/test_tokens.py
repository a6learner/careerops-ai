from datetime import timedelta
from uuid import uuid4

import jwt
import pytest

from careerops.security.tokens import TokenIssuer


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
