# CareerOps AI P0 Demo Script

Target duration: 3–5 minutes. Use only the isolated fake-provider stack. Start
within 25 minutes of presenting so the 30-minute access token cannot expire
during the demo.

## Preflight

```powershell
.\scripts\local_full_stack_acceptance.ps1 -RunId demo-check -DemoRehearsal
```

For a live presentation, start the ordinary Compose stack with all three
providers set to `fake`, verify frontend `/healthz` and `/readyz`, and open the
frontend origin. Never use real-provider credentials for this demo.

## Timed Walkthrough

| Time | Browser action | Narration |
|---|---|---|
| 0:00–0:25 | Register and arrive at Dashboard | “The browser talks only to Next.js. The bearer token stays in a host-only HttpOnly cookie; FastAPI remains the authorization boundary.” |
| 0:25–0:55 | Add one Experience with Python/FastAPI/PostgreSQL evidence | “Experiences are user-owned, versioned, soft-deletable records. The matcher may cite only stored source text.” |
| 0:55–1:25 | Add a Job requiring Python and Kubernetes | “Jobs use optimistic locking and cursor pagination. This demo uses synthetic content.” |
| 1:25–1:55 | Parse the description and show two structured requirements | “The API only queues durable work. The worker calls the fake parser and persists traceable source spans.” |
| 1:55–2:40 | Run Analysis; point to the Python quote and Kubernetes gap | “Retrieval and matching happen in the worker. Positive evidence must pass schema, ownership/source validation, and database constraints. Missing evidence stays a gap; the system never invents experience.” |
| 2:40–3:15 | Create an Action Item from the gap; update Job to Applied | “The gap becomes explicit work, while version checks prevent silent concurrent overwrites.” |
| 3:15–3:45 | Mark the Action Item done | “The task keeps its analysis provenance and remains usable even if the Job is archived.” |
| 3:45–4:10 | Open Dashboard and show Applied=1 and Completed tasks=1 | “Redis accelerates this read, but PostgreSQL is authoritative and the cache fails open.” |
| 4:10–4:30 | Close on architecture and limitations | “This is local synthetic evidence, not production availability. Refresh tokens are deferred, so expiry requires login again; cloud deployment is a later stage.” |

## Failure-Safe Presentation Notes

- If readiness is not green, do not continue; show the failing dependency rather
  than changing data manually.
- If a workflow fails, show the request ID or durable error code. Do not switch to
  a real provider as a recovery shortcut.
- Do not claim production latency. The saved local P50/P95 evidence is in
  `docs/metrics/2026-10-10-read-endpoint-performance.md`.
- Stop with `docker compose down`. Add `-v` only for an intentionally disposable
  demo database.

## Rehearsal Evidence

The completed rehearsal result is recorded in
`docs/metrics/2026-10-10-p0-demo-rehearsal.md`.
