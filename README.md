# CareerOps AI

CareerOps AI is a backend-first project for matching internship job requirements against a student's real experience evidence. The product uses AI, but the engineering focus is reliability: asynchronous work, idempotency, database constraints, caching, observability, and repeatable tests.

## Current Status

This repository has a backend-first FastAPI foundation with health endpoints, local PostgreSQL and Redis dependencies, strict typing, import boundary checks, CI scaffolding, email/password authentication, signed access tokens, a reusable current-user dependency, user-owned Experiences and Jobs CRUD, and worker-backed idempotent parse runs that turn immutable JD snapshots into candidate-grounded structured requirements through a fake or Groq adapter. A versioned synthetic evaluation set records parser quality without putting live model calls in CI. Evidence-backed Analysis Runs provide idempotent submission and polling, deterministic Top-5 candidate retrieval, worker-only fake matching, changed-input detection, citation validation, atomic result writes, and PostgreSQL constraints for complete verdict integrity. Job-scoped Action Items support manual creation, gap provenance, idempotent retries, optimistic updates, and archived-Job retention. The Dashboard summarizes active Job and Action Item counts through a disposable Redis cache. Experience embeddings now have durable, version-bound fake generation, stale-result fencing, and PostgreSQL-backed recovery. Reviewed multi-profile development labels record the harder lexical v2 baseline while a separate holdout remains sealed. A default-off evaluation path can compare lexical, Gemini vector, and weighted-RRF hybrid retrieval on synthetic development data without changing production Analysis Runs. No real embedding evaluation has been run or saved yet. Pgvector production retrieval and a real evidence matcher remain later quality-focused slices.

## Architecture Direction

```mermaid
flowchart TD
    Web[Next.js demo UI] --> API[FastAPI API service]
    API --> Postgres[(PostgreSQL + pgvector)]
    API --> Redis[(Redis)]
    Redis --> Worker[Worker service]
    Worker --> Postgres
    Worker --> LLM[LLM provider adapter]
```

The API service will never call the LLM directly. Model calls belong in the worker so request latency stays predictable and tests can replace the provider with a fake implementation.

## Local Setup

Create a project-local virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev,worker]"
```

Run the API through the virtual environment:

```powershell
.\.venv\Scripts\uvicorn careerops.main:create_app --factory --reload
```

Start local infrastructure:

```powershell
docker compose up -d postgres redis
```

Run the worker in a separate terminal:

```powershell
.\.venv\Scripts\dramatiq careerops.workers.tasks --processes 1 --threads 4
```

The checked-in `.env.example` defaults to the deterministic `fake` provider.
To run Groq locally, copy the example to the ignored `.env`, set
`CAREEROPS_LLM_PROVIDER=groq`, and add `CAREEROPS_LLM_API_KEY`. Never commit the
key. Automated tests remain fake or mock-backed unless the live-test flag is
explicitly enabled.

Recover queued work and stale running work from PostgreSQL:

```powershell
.\.venv\Scripts\python -m careerops.workers.recovery
.\.venv\Scripts\python -m careerops.workers.analysis_recovery
.\.venv\Scripts\python -m careerops.workers.embedding_recovery
```

Apply database migrations:

```powershell
.\.venv\Scripts\alembic upgrade head
```

Useful checks:

```powershell
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\python -m mypy
.\.venv\Scripts\ruff check .
.\.venv\Scripts\lint-imports
```

Run the small real-provider compatibility test intentionally:

```powershell
$env:CAREEROPS_RUN_LLM_INTEGRATION='1'
.\.venv\Scripts\python -m pytest tests/integration/test_groq_live.py -s
Remove-Item Env:CAREEROPS_RUN_LLM_INTEGRATION
```

Run the labeled development-set evaluation intentionally, always choosing a new
output filename so historical evidence remains intact:

```powershell
.\.venv\Scripts\python -m careerops.evaluation.run_requirement_parser `
  --dataset evals/job_requirements_v1.json `
  --output docs/metrics/YYYY-MM-DD-groq-requirement-eval.json `
  --git-revision <commit-or-working-tree-label>
```

Evaluate the current lexical evidence retriever offline, again choosing a new
output filename for every saved comparison:

```powershell
.\.venv\Scripts\python -m careerops.evaluation.run_evidence_retrieval `
  --dataset evals/evidence_retrieval_v1.json `
  --output docs/metrics/YYYY-MM-DD-lexical-retrieval-baseline.json `
  --git-revision <commit-or-working-tree-label>
```

Run retrieval evaluation v2 only with the approved manifest and development split:

```powershell
.\.venv\Scripts\python -m careerops.evaluation.run_evidence_retrieval_v2 `
  --experiences evals/evidence_retrieval_v2/experiences.json `
  --queries evals/evidence_retrieval_v2/development_queries.json `
  --review-manifest evals/evidence_retrieval_v2/review_manifest.json `
  --output docs/metrics/YYYY-MM-DD-lexical-retrieval-v2-development.json `
  --git-revision <commit-or-working-tree-label>
```

The command rejects holdout queries. Keep the holdout sealed until lexical, vector,
and hybrid candidates and parameters are frozen for their one-time comparison.

Exercise the P1-3a evaluation pipeline offline with its deterministic fake provider:

```powershell
.\.venv\Scripts\python -m careerops.evaluation.run_embedding_retrieval_v2 `
  --experiences evals/evidence_retrieval_v2/experiences.json `
  --queries evals/evidence_retrieval_v2/development_queries.json `
  --review-manifest evals/evidence_retrieval_v2/review_manifest.json `
  --lexical-baseline docs/metrics/2026-09-21-lexical-retrieval-v2-development.json `
  --cache "$env:TEMP\p1-3a-fake-cache.json.gz" `
  --output "$env:TEMP\p1-3a-fake-comparison.json" `
  --git-revision <commit-or-working-tree-label> `
  --provider fake
```

Run the real Gemini development evaluation only after explicit authorization. Use
new cache and output filenames, verify the active Google AI Studio project quota,
and send only the checked-in synthetic data. Store the key only in the ignored
repository-root `.env` file:

```dotenv
CAREEROPS_GEMINI_API_KEY=<paste-the-key-here>
```

Do not put the key in `.env.example`, a command, source code, or chat. The key is
read from `.env`; the one-run opt-in remains a temporary environment variable:

```powershell
$env:CAREEROPS_RUN_EMBEDDING_EVAL='1'
.\.venv\Scripts\python -m careerops.evaluation.run_embedding_retrieval_v2 `
  --experiences evals/evidence_retrieval_v2/experiences.json `
  --queries evals/evidence_retrieval_v2/development_queries.json `
  --review-manifest evals/evidence_retrieval_v2/review_manifest.json `
  --lexical-baseline docs/metrics/2026-09-21-lexical-retrieval-v2-development.json `
  --cache docs/metrics/YYYY-MM-DD-gemini-embedding-2-development-vectors.json.gz `
  --output docs/metrics/YYYY-MM-DD-gemini-embedding-2-development-comparison.json `
  --git-revision <commit-or-working-tree-label> `
  --provider gemini
Remove-Item Env:CAREEROPS_RUN_EMBEDDING_EVAL
```

The Gemini path is disabled unless both the explicit flag and key are present. It
uses one document batch and one development-query batch with one attempt each,
requires exactly 1536 finite non-zero vectors, refuses output overwrite, and never
accepts the holdout split.

P1-3b has a separate one-time holdout runner. Do not run it without explicit
holdout authorization. It verifies the committed P1-3a report and vector-cache
hashes, reuses the 40 frozen document vectors, and submits only the 20 synthetic
holdout queries in one single-attempt batch. The vector threshold `0.65`, hybrid
threshold `0.65`, and hybrid lexical weight `0.50` cannot be overridden:

```powershell
$env:CAREEROPS_RUN_EMBEDDING_HOLDOUT='1'
.\.venv\Scripts\python -m careerops.evaluation.run_embedding_holdout_v2 `
  --experiences evals/evidence_retrieval_v2/experiences.json `
  --holdout-queries evals/evidence_retrieval_v2/holdout_queries.json `
  --review-manifest evals/evidence_retrieval_v2/review_manifest.json `
  --frozen-development-report docs/metrics/2026-10-01-gemini-embedding-2-development-comparison.json `
  --frozen-development-cache docs/metrics/2026-10-01-gemini-embedding-2-development-vectors.json.gz `
  --cache docs/metrics/YYYY-MM-DD-gemini-embedding-2-holdout-queries.json.gz `
  --output docs/metrics/YYYY-MM-DD-gemini-embedding-2-holdout-comparison.json `
  --git-revision <commit-or-working-tree-label>
Remove-Item Env:CAREEROPS_RUN_EMBEDDING_HOLDOUT
```

The holdout runner has no fake CLI mode and no parameter grid. Default tests use
development-derived toy queries marked as holdout, not the real holdout file. A
provider failure saves an incomplete query cache and writes no comparison report.

Using the explicit `.venv` paths keeps project dependencies out of the global Python or Anaconda environment.

## API Surface

- `GET /healthz` checks whether the API process is alive.
- `GET /readyz` checks whether required dependencies are reachable.
- `POST /api/v1/auth/register` creates a user with a hashed password.
- `POST /api/v1/auth/login` verifies credentials and returns a bearer access token.
- `GET /api/v1/auth/me` returns the current user for a valid bearer access token.
- `GET /api/v1/experiences` lists the current user's active experiences.
- `POST /api/v1/experiences` creates an experience owned by the current user.
- `GET /api/v1/experiences/{id}` returns one owned active experience.
- `PATCH /api/v1/experiences/{id}` updates one owned active experience with `If-Match` optimistic locking.
- `DELETE /api/v1/experiences/{id}` soft-deletes one owned active experience.
- `GET /api/v1/jobs` lists the current user's active jobs with optional status filtering and cursor pagination.
- `POST /api/v1/jobs` creates a target job description owned by the current user.
- `GET /api/v1/jobs/{id}` returns one owned active job.
- `PATCH /api/v1/jobs/{id}` updates one owned active job with `If-Match` optimistic locking.
- `DELETE /api/v1/jobs/{id}` soft-deletes one owned active job.
- `POST /api/v1/jobs/{id}/parse-runs` creates or reuses a queued idempotent parse run for one owned active job; a key can be replayed only while that job's parse input is unchanged.
- `GET /api/v1/jobs/{id}/parse-runs/{run_id}` returns one owned parse run with structured requirements.
- `POST /api/v1/jobs/{id}/analysis-runs` creates or reuses a queued idempotent Analysis Run for an explicit successful Parse Run and the current active experience-library fingerprint.
- `GET /api/v1/jobs/{id}/analysis-runs/{run_id}` returns one owned Analysis Run with validated evidence matches and explicit gaps.
- `GET /api/v1/action-items` lists owned tasks with optional Job/status filters and cursor pagination, including archived-Job state.
- `POST /api/v1/action-items` idempotently creates a manual task or one linked to an actionable Evidence Match.
- `PATCH /api/v1/action-items/{id}` updates title or status with `If-Match` optimistic locking, including after its Job is archived.
- `GET /api/v1/dashboard/summary` returns the current user's active Job and Action Item status totals, cached in Redis with PostgreSQL fallback.

The backend MVP core loop now reaches the Dashboard summary. The embedding lifecycle is ready, and the deterministic lexical/skill retriever has reviewed v1 and v2 development baselines. Analysis Runs intentionally continue to use that unchanged retriever. P1-3a adds only a default-off development evaluation path; no real embedding result has been generated. The v2 holdout remains sealed, and pgvector-backed production hybrid retrieval remains a separate later stage.

## Key Decisions

- Python is used with strict typing discipline because the project targets backend systems plus LLM governance, not a language showcase.
- PostgreSQL is the only source of truth. Redis may be cleared and rebuilt.
- Dramatiq is the worker queue because its Redis integration is small and direct for this project size. PostgreSQL remains the durable task source and can rebuild queued delivery.
- Database constraints will enforce core invariants, especially the rule that positive evidence matches cannot be stored without real evidence.
