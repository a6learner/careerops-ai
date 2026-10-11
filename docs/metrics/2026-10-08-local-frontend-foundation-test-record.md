# Local Frontend Foundation Test Record — 2026-10-08

## Scope

This record covers P1-9a only: the Next.js foundation, visual shell, registration
and login UI, HttpOnly session cookie, same-origin FastAPI proxy policy, and
frontend CI gates. It does not claim that Experience, Job, Parse, Analysis, Action
Item, or Dashboard workflows are complete.

- Branch: `codex/p1-3b-embedding-holdout`
- Base HEAD: `96774d5`
- Local Node.js: 24.14.1
- Package manager: npm 11.6.0
- Backend schema, migrations, or public API changes: none
- Provider calls or holdout access: none
- P1-8 test rerun: none

## Verification

| Check | Result |
|---|---|
| ESLint | passed |
| Strict TypeScript | passed |
| Vitest | 10 passed across 4 files |
| Production dependency audit | 0 vulnerabilities |
| Optimized Next.js build | passed; 12 routes generated |

The tests cover:

- HttpOnly, SameSite=Lax, path, lifetime, and production Secure cookie flags;
- exact same-origin enforcement for mutation requests;
- proxy path allowlisting and denial of direct auth login/register proxying;
- trusted Authorization injection and filtering of browser Cookie/Authorization;
- preservation of Content-Type, Retry-After, and X-Request-ID only;
- structured backend error and safe unexpected-response handling;
- login success, registration-before-login ordering, and credential-error display.

## Environment Findings

The restricted Windows sandbox denied Vitest temporary-file renames and Next.js
path canonicalization. Both commands passed when rerun with normal host permissions.
No application or test assertion was weakened.

Vitest 5 also selected a Rolldown optional native binding that npm omitted on this
host. The project uses Vitest 4.1.11 instead; its Vite-based path passed the same
tests without deleting the lockfile or forcing optional native packages.

The full `npm audit` reports five high-severity entries in the development-only
`eslint-config-next -> fast-glob -> micromatch -> braces` chain. The registry has
no patched `braces` version, and npm's suggested force fix downgrades
`eslint-config-next` across a major Next.js compatibility boundary. The saved
runtime gate is `npm audit --omit=dev`, which reports zero vulnerabilities. This is
a documented tooling limitation, not a claim that the full development tree is
clean.

## Boundaries

- No browser-driven request against a running FastAPI/PostgreSQL stack was part of
  this slice; that begins with the resource pages and full local acceptance.
- The current access token has no refresh flow and expires after 30 minutes.
- The UI shell contains explicit placeholders and no invented Dashboard counts.
- The frontend is not yet containerized; that remains P1-10 scope.
