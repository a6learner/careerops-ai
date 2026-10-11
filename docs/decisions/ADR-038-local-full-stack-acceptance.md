# ADR-038: Local Full-Stack Acceptance

## Status

Accepted

## Context

P1-9 completed the browser workflows, but the frontend still ran as a separate
host process. P1-10 must prove that a fresh local environment can start and use
the complete product without changing the backend API, enabling permissive CORS,
calling a real model, or manually editing PostgreSQL.

The same backend image serves both API and worker roles. Its HTTP readiness probe
is correct for the API but cannot describe a worker process. The Next.js BFF also
has two distinct addresses in Compose: the internal FastAPI address and the
browser-visible frontend origin. Treating those as interchangeable breaks the
exact-Origin mutation defense.

## Decision

- Build the Next.js application as a standalone, multi-stage Node 22 image and
  run it as the image's non-root `node` user.
- Add `frontend` to Compose while preserving separate one-shot `migrate`, API,
  worker, PostgreSQL, and Redis services.
- Keep the browser on the Next.js origin. The BFF uses the server-only
  `CAREEROPS_API_BASE_URL=http://api:8000`; FastAPI gains no browser CORS policy
  and no Nginx layer is added.
- Configure `CAREEROPS_FRONTEND_ORIGIN` as the canonical browser-visible origin.
  Unsafe BFF requests require an exact match and fail closed if the configured
  value is invalid.
- Expose dependency-free frontend `/healthz` and dependency-aware `/readyz`.
  Readiness succeeds only when the frontend can obtain a successful API
  readiness response.
- Disable the inherited API HTTP healthcheck for the worker role. The worker is
  exercised through queued Parse, embedding, and Analysis work instead.
- Use a separate acceptance Compose override that sets parser, embedding, and
  matcher providers to `fake`, clears provider keys, and disables live gates.
- Run one Chromium Playwright scenario through the public frontend only. The
  harness creates a unique Compose project, checks configuration and runtime
  provider values, verifies migration and non-root boundaries, and performs
  exact-project cleanup in `finally`.

## Alternatives Considered

- Direct browser calls to FastAPI with CORS: rejected because it bypasses the
  accepted same-origin session boundary and creates a broader browser contract.
- Nginx in front of both applications: rejected because Next.js already owns the
  BFF boundary and an additional proxy adds no P1-10 capability.
- Reuse the root `.env` for acceptance: rejected because a developer may select
  a real provider there; acceptance must be deterministic and cost-free.
- Use only API requests for the smoke flow: rejected because P1-10 specifically
  needs proof that browser forms, cookies, polling, worker execution, and rendered
  results work together.
- Run Playwright inside the frontend production image: rejected because browser
  binaries would enlarge the runtime image. The test runner remains a pinned
  development dependency on the host.

## Consequences

The local product now has the same service boundaries expected by the
platform-neutral release contract. Browser traffic remains same-origin and the
API remains private to server-side frontend calls at the UI boundary.

The public frontend origin is explicit configuration and must change with the
published host or port. Frontend readiness is intentionally coupled to API
readiness, while liveness remains process-only. The acceptance harness deletes
its isolated database volume, so its project identity and cleanup scope are
safety-critical.

Playwright is a new major development-only dependency. It adds one browser binary
installation step, but does not enter the production image or runtime dependency
set.

## Verification Or Evidence

- Focused route/session tests cover frontend health, readiness, and configured
  public-origin validation.
- ESLint, strict TypeScript, production dependency audit, and optimized frontend
  image build pass.
- The P1-10 harness completed a fresh isolated startup and the entire browser
  core loop with all providers verified as `fake`, then removed its labeled
  containers, network, and volume.
- Detailed evidence is stored in
  `docs/metrics/2026-10-10-local-full-stack-acceptance.md`.

## Revisit If

- A cloud platform supplies a different probe, release-job, or public-origin
  mechanism.
- Multiple public frontend origins become a real product requirement.
- A worker-native heartbeat is needed for production operations.
