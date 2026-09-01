# 0004 Password Hashing

## What Changed

This step added the first authentication building block:

- `pwdlib[argon2]` dependency in `pyproject.toml`.
- `src/careerops/security/passwords.py` with a small `PasswordHasher` wrapper.
- `tests/test_passwords.py` covering hash and verify behavior.
- `docs/decisions/ADR-004-password-hashing.md` recording the password storage decision.

No register or login endpoint was added yet. This step isolates password storage before we add API and database write behavior.

## Why It Exists

Users will authenticate with email and password. The system must store something that proves the user can log in later, but it must not store the raw password.

A password hash is one-way:

```text
password -> hash
hash -> original password should be infeasible
```

During login, we do not decrypt the password. We hash/verify the submitted password against the stored hash using the password hashing library.

## Failure Modes It Prevents

- If raw passwords are stored, a database leak exposes user credentials immediately.
- If a fast hash like plain SHA-256 is used, attackers can guess huge numbers of passwords cheaply offline.
- If every identical password produces the same stored value, attackers can identify users who share a password.
- If password-library calls are scattered through the codebase, changing the policy later becomes risky.

## How To Verify It

Run:

```powershell
.\.venv\Scripts\python -m pytest tests/test_passwords.py
```

Expected behavior:

- the stored hash is not equal to the password
- the correct password verifies
- the wrong password fails
- hashing the same password twice produces different hashes

## What You Must Understand

Level 1 concepts:

- Passwords must be hashed, not encrypted or stored raw.
- Password hashing should be intentionally expensive to slow offline guessing.
- Salts make identical passwords produce different hashes.

Level 2 concepts:

- `PasswordHasher` is our local wrapper around a third-party library.
- Future auth service code should call this wrapper instead of importing `pwdlib` directly.
- Tests describe the security behavior we rely on before registration/login exists.

## Knowledge Check

1. Why do we verify a password instead of decrypting the stored hash?
2. Why is plain SHA-256 a bad password storage choice even though SHA-256 is a real hash algorithm?
3. Why should two users with the same password still have different stored hashes?
4. Why wrap `pwdlib` in our own `PasswordHasher` instead of importing it inside every auth function?
5. What is the benefit of testing password hashing before implementing `/auth/register`?
