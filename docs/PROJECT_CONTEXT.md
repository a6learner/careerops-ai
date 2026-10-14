# CareerOps AI Project Context

CareerOps AI is a portfolio-grade backend project for a CS master's student preparing for 2027 Summer software engineering, backend, and AI engineering internships.

The project has three purposes, in priority order:

1. Become a backend project strong enough to put on a resume and discuss deeply in interviews.
2. Help the author practice the full backend development loop: requirements, design, implementation, tests, deployment, observability, and review.
3. Solve a real personal workflow: matching job descriptions to verified personal experiences.

The recruiting signal target is approximately:

| Area | Weight |
|---|---:|
| Backend and systems engineering | 65% |
| AI engineering | 25% |
| Frontend | 10% |

When trade-offs conflict, prefer the choice that better demonstrates backend engineering judgment.

## Product Positioning

CareerOps AI is not intended to be a general AI assistant, a thin LLM wrapper, or a portfolio stuffed with features.

The core claim is:

> A reliable backend service with explicit concurrency control, transaction boundaries, idempotency, caching, observability, and a safe boundary around an unreliable AI dependency.

The interview story should be about system design, data integrity, failure handling, and measurable behavior. The LLM is part of the system, but it is not the system.

## User

The MVP serves one user type: a CS student applying to SWE / backend / AI internships in the United States.

This user tracks multiple jobs, owns a set of project/course/work experiences, and needs help connecting each job requirement to real evidence from those experiences.

The MVP does not serve recruiters, teams, or enterprise hiring workflows.

## Core Loop

The MVP is successful only when this flow works end to end:

```text
register/login -> build experience library -> save job description
-> parse structured requirements -> match requirements to real evidence
-> review evidence and gaps -> create tasks -> track application status
-> view progress in a dashboard
```

## Product Integrity Principle

The system must never say the user has a skill or experience without evidence.

If evidence is missing, the system should explicitly represent that as a gap or insufficient evidence. This is both an ethical product requirement and the project's strongest engineering idea.

## Author Learning Context

The author already has experience with Python, MySQL, a complete RAG workflow, and OpenAI-compatible APIs.

The author has used but wants more practice with FastAPI, Docker, and pytest.

The project should deliberately build skill in PostgreSQL, Redis, worker queues, cloud deployment, and React/Next.js. When those technologies appear for the first time, Codex should explain the engineering reason and failure mode, not just add code.

## Time And Scope

The intended development budget is about 8-10 effective development weeks, with roughly 12 hours per week.

The project should freeze feature work around the seventh effective development week. After that, prioritize tests, deployment, docs, demo quality, metrics, and interview preparation.

If schedule pressure appears, cut scope before cutting tests, deployment, or evidence guarantees.

## Current Delivery Sequence

As of 2026-10-10, use this sequence when an older stage suggestion conflicts
with it. P1-8 through P1-10 established the local operational and browser core
loop. P1-11 closes the remaining P0 evidence and contract gaps before local
product hardening or cloud work.

### P1-9: Local Frontend MVP

Status: completed locally. The minimal Next.js demo layer exposes authentication,
Experiences, Jobs, Parse and Analysis Runs, evidence/gaps, Action Items, and the
Dashboard through the accepted same-origin session boundary. It preserves the
existing API and displays actionable HTTP and durable-workflow failures.

### P1-10: Local Full-Stack Acceptance

Containerize the frontend and integrate it with the API, worker, PostgreSQL,
Redis, and migration release step. Validate a clean local startup and one full
browser-driven core-loop run using fake providers, without manual database
intervention. Add frontend-focused automated tests and proportionate end-to-end
coverage; approve any major new test dependency before adding it.

Acceptance: a fresh local environment can start the complete product using the
documented workflow and complete the core loop through the browser.

Status: completed locally on 2026-10-10. The saved acceptance used a fresh,
isolated Compose project and volume, forced parser, embedding, and matcher to
deterministic fake providers, completed the core loop in Chromium without direct
database changes, and verified exact project cleanup. Cloud deployment and P1-11
remain separate stages.

### P1-11: P0 Closure

Close the remaining delivery evidence and contract gaps: save local pagination
and read-endpoint P50/P95 evidence including the 5,000-Job case; demonstrate the
supported Alembic migration rollback boundary; run a fresh-database migration
check in CI; add the 3-5 minute demo script; and explicitly decide whether the
documented refresh-token endpoint is implemented or deferred as a known MVP
limitation. Any public API or authentication contract change still requires
author approval.

Acceptance: every P0 delivery claim is either verified by a saved repository artifact
or explicitly recorded as a known limitation, with no invented metrics.

Status: implemented and verified locally on 2026-10-10. The 5,000-Job benchmark,
latest one-step rollback drill, fake-provider demo rehearsal, refresh-token
deferral, and final evidence/limitation matrix are saved. The fresh-database CI
job is configured and its commands were exercised locally; a GitHub-hosted green
run remains pending commit and push authorization.

### CV Import And Assisted Job Discovery

Status: completed locally on 2026-10-11. Full backend and frontend quality
gates, fresh migration and drift checks, a worker-image LibreOffice RTF smoke,
and the isolated fake-provider browser flow passed. The exact evidence and
limits are saved in
`docs/metrics/2026-10-11-cv-import-job-discovery-test-record.md`.

This is one review-first feature rather than a sequence of route-numbered
milestones. It adds worker-backed import for text PDF, DOCX, DOC, ODT, RTF,
UTF-8 TXT, and Markdown, with Google Docs supported through DOCX/PDF export.
Every generated Experience draft retains exact CV source references; no formal
Experience or embedding run exists until user confirmation. Scanned-PDF OCR,
Google OAuth, and new employer/date fields are deferred.

Assisted job discovery uses a neutral worker adapter and a deterministic fake
provider. Results retain provider identity, source URL, and observation time.
The user reviews a Job draft and must paste a complete description when the
source supplies only a summary. No real search provider, generic URL fetching,
broad scraping, per-user provider keys, or automatic applications are included.
Manual Experience and Job entry remains unchanged.

ADR-040 records the format, worker, draft, provenance, retention, and provider
boundaries. Learning note 0046 explains the transaction and authorization
behavior. Development uses focused tests; completion requires one consolidated
backend/frontend quality pass and one fake-provider browser flow through import,
discovery, Parse, Analysis, Action Items, and Dashboard.

### P1-13: Local Product Hardening

After P1-12, improve accessibility, small-screen behavior, actionable error and
empty states, and focused usability defects without a broad UI redesign.

### P1-14: Cloud Deployment

Choose a deployment provider and add provider-specific infrastructure only
after P1-9 through P1-13 pass locally. Then configure secrets, TLS, release
migrations, health probes, rollback, and a production smoke test without
weakening the platform-neutral deployment contract.

Acceptance: the locally accepted product is deployed and verified through its
documented production workflow. Local success is not presented as production
availability evidence.

## Source Material

- Detailed MVP scope: `docs/CareerOps AI MVP 产品范围与 Non-goals.md`
- User stories and use cases: `docs/product/user-stories-and-use-cases.md`
- Programming language research: `docs/52 条 2027 届实习 JD 语言要求调研.md`
- Decision records: `docs/decisions/`
- Learning notes: `docs/learning/`
- Measured evidence: `docs/metrics/`
