# ADR-004: Store Passwords With Argon2id Hashing

## Status

Accepted

## Context

CareerOps AI needs email and password authentication. The database must never store raw passwords because a database leak would immediately expose user credentials.

Password storage needs a purpose-built password hashing algorithm, not a fast general-purpose hash. Fast hashes make offline guessing cheaper for attackers.

## Decision

Use `pwdlib[argon2]` and its recommended password hash configuration.

Application code wraps the third-party library behind `PasswordHasher` in `src/careerops/security/passwords.py`. Auth services will depend on this local boundary rather than importing password-library details directly.

## Alternatives Considered

- Store raw passwords: unacceptable because a database leak would reveal credentials.
- Use SHA-256 directly: too fast for password storage and easy to misuse without per-password salts and work factors.
- Use bcrypt: mature and acceptable, but Argon2id is a modern memory-hard default and fits the current Python ecosystem cleanly through `pwdlib`.

## Consequences

Password verification becomes intentionally more expensive than a normal hash, which helps resist brute-force attacks after a credential database leak.

The trade-off is an additional dependency and slightly slower tests for password behavior. This is acceptable because authentication security is a core backend concern.

## Verification Or Evidence

`tests/test_passwords.py` verifies that:

- hashes do not equal raw passwords
- the original password verifies
- a wrong password is rejected
- hashing the same password twice produces different hashes because salts are used

## Revisit If

Revisit if the library becomes unmaintained, if deployment constraints make Argon2id memory settings impractical, or if a security review recommends a different password hashing policy.
