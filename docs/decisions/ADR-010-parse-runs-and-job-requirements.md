# ADR-010: Parse Runs And Job Requirements

## Status

Accepted

## Context

CareerOps AI now has authenticated users, an experience library, and saved job
descriptions. The next product step is `US-004: Extract Job Requirements`: turn
a raw job description into structured requirements that the user can inspect and
that future analysis runs can match against experience evidence.

The project constraint remains: the API service must never call the LLM
directly. Model calls belong behind worker-side workflow boundaries.

## Decision

Add `parse_runs` and `job_requirements` tables plus nested job endpoints:

```text
POST /api/v1/jobs/{job_id}/parse-runs
GET /api/v1/jobs/{job_id}/parse-runs/{parse_run_id}
```

The POST endpoint requires `Idempotency-Key` and returns `202 Accepted`.

For this first slice, the service uses a deterministic local fake parser. It
splits raw JD text into simple requirement candidates, classifies them into the
current requirement categories, records source spans, and writes a succeeded
parse run plus requirements in one transaction.

The fake parser is not an AI quality claim. It exists so the resource model,
authorization, idempotency, response shape, and source-span persistence can be
tested before adding the real worker and LLM adapter.

## Alternatives Considered

- Call an LLM directly from the API: rejected because it violates the core
  architecture constraint and would make latency and tests unpredictable.
- Build the full worker queue in the same change: rejected because it combines
  too many concepts. Parse run persistence and API contracts are a useful slice
  on their own.
- Store parsed requirements as JSON on `parse_runs`: rejected because
  `job_requirements` are first-class rows that future analysis and evidence
  matching will reference.
- Skip source spans until the LLM stage: rejected because source spans are part
  of the anti-hallucination contract and should be present from the first parse
  result model.

## Consequences

The MVP flow now reaches "save job description -> submit parse run -> review
structured requirements."

The current implementation completes parse runs immediately with a fake parser.
The next worker milestone should preserve the API contract while moving parsing
execution behind a real queue and LLM adapter.

`parse_runs.user_id` is redundant with `jobs.user_id` by design. It keeps
authorization queries simple and gives future run lists a direct owner column.

## Verification Or Evidence

Verified locally:

- `.\.venv\Scripts\python -m pytest`
- `.\.venv\Scripts\python -m mypy`
- `.\.venv\Scripts\ruff check .`
- `.\.venv\Scripts\lint-imports`
- `.\.venv\Scripts\alembic upgrade head`
- Integration tests with `CAREEROPS_RUN_INTEGRATION=1`
- PostgreSQL table inspection for `parse_runs` and `job_requirements`

No parsing quality metric is claimed. The parser is deterministic test
infrastructure for the resource boundary.

## Revisit If

Revisit when implementing the worker-backed parser, adding retry states,
introducing prompt/model versioning beyond `parse-v1`, or enforcing stronger
programmatic validation of source spans from real model output.
