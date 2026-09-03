from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt

from careerops.domain.errors import ExpiredTokenError, InvalidTokenError


@dataclass(frozen=True)
class AccessToken:
    value: str
    token_type: str = "bearer"


@dataclass(frozen=True)
class TokenIssuer:
    secret: str
    expires_after: timedelta
    algorithm: str = "HS256"

    def issue_access_token(self, user_id: UUID) -> AccessToken:
        now = datetime.now(UTC)
        payload = {
            "sub": str(user_id),
            "iat": now,
            "exp": now + self.expires_after,
        }
        return AccessToken(value=jwt.encode(payload, self.secret, algorithm=self.algorithm))


@dataclass(frozen=True)
class TokenVerifier:
    secret: str
    algorithm: str = "HS256"

    def verify_access_token(self, token: str) -> UUID:
        try:
            payload = jwt.decode(token, self.secret, algorithms=[self.algorithm])
            subject = payload.get("sub")
            if not isinstance(subject, str):
                raise InvalidTokenError()
            return UUID(subject)
        except jwt.ExpiredSignatureError as exc:
            raise ExpiredTokenError() from exc
        except (jwt.InvalidTokenError, ValueError) as exc:
            raise InvalidTokenError() from exc
