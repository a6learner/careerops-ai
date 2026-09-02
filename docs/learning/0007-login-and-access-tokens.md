# 0007 Login And Access Tokens

## What Changed

This step added:

- `POST /api/v1/auth/login`
- `src/careerops/security/tokens.py`
- JWT settings in `src/careerops/core/config.py`
- `CAREEROPS_JWT_SECRET` and `CAREEROPS_ACCESS_TOKEN_EXPIRE_MINUTES` in `.env.example`
- login service and repository support
- tests for tokens and login behavior

Login returns:

```json
{
  "access_token": "...",
  "token_type": "bearer"
}
```

## Why It Exists

Registration creates a user. Login proves that a caller knows that user's password and gives the client a temporary credential for later requests.

The access token is signed. That means the server can detect if a client changes the token payload.

## Failure Modes It Prevents

- Returning different errors for unknown email and wrong password, which would leak which accounts exist.
- Letting clients invent a user id by sending an unsigned token.
- Creating access tokens that never expire.
- Using a too-short HMAC secret for HS256 signing.

## How To Verify It

Default checks:

```powershell
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\python -m mypy
.\.venv\Scripts\ruff check .
.\.venv\Scripts\lint-imports
```

With PostgreSQL running:

```powershell
docker compose up -d postgres
.\.venv\Scripts\alembic upgrade head
$env:CAREEROPS_RUN_INTEGRATION = "1"
.\.venv\Scripts\python -m pytest tests/integration/test_auth_register_postgres.py
Remove-Item Env:\CAREEROPS_RUN_INTEGRATION
```

## What You Must Understand

Level 1 concepts:

- Authentication answers "who are you?"
- `401` means credentials are missing or invalid.
- Unknown email and wrong password should produce the same login error.
- JWTs must be signed so identity claims cannot be changed by the client.
- Access tokens should expire.

Level 2 concepts:

- `TokenIssuer` wraps `PyJWT`.
- `sub` stores the authenticated user's id.
- `iat` records issue time and `exp` records expiration.
- JWT secret comes from settings and must not be hardcoded differently around the codebase.

## Knowledge Check

1. Why should login return the same error for an unknown email and a wrong password?
2. What does JWT signing prevent?
3. Why does an access token need an expiration time?
4. Why do we put the user id in `sub` instead of sending the whole user object in the token?
5. What auth feature is still missing before `/experiences` can know the current user?
