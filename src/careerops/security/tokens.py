from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt


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
