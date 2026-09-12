# 0016 Analysis Run End-To-End

## What Changed

The evidence integrity foundation is now connected into a usable asynchronous flow:

- authenticated submit and query endpoints for Analysis Runs;
- idempotent queued-run creation tied to an explicit successful Parse Run;
- deterministic Top-5 lexical and skill candidate retrieval;
- a worker-only fake evidence matcher;
- strict requirement coverage and evidence citation validation;
- atomic succeeded-result persistence;
- conditional task claiming and stale-run recovery;
- one database-enforced verdict per run and requirement.

This slice does not call Groq and does not generate embeddings.

## Why It Exists

Evidence validation is useful only when it surrounds the complete workflow. The API
must accept work without waiting, Redis must remain disposable, workers must tolerate
duplicate delivery, and users must be able to distinguish real gaps from invalid
model claims.

The deterministic retriever and fake matcher isolate application correctness from
retrieval quality and provider behavior. They let tests prove the run lifecycle and
integrity guarantees before pgvector or a real evidence matcher is introduced.

## Failure Modes It Prevents

- The API accidentally choosing a stale or unintended parse result.
- Repeated clicks creating duplicate work for the same idempotency key.
- Concurrent retries with the same idempotency key creating duplicate runs.
- Redis downtime deleting work that the API already accepted.
- Duplicate queue messages running the matcher twice.
- Experience edits causing the worker to analyze content different from submission.
- A matcher omitting a requirement, duplicating one, or inventing another ID.
- Positive claims citing another user, a non-candidate experience, a stale version,
  or text outside the experience source.
- A succeeded run containing duplicate or incomplete evidence rows.
- A crashed worker remaining in running forever without a recovery path.

## How To Verify It

Run offline checks:

```powershell
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\python -m mypy
.\.venv\Scripts\ruff check .
.\.venv\Scripts\lint-imports
```

Run PostgreSQL and Redis integration tests:

```powershell
docker compose up -d postgres redis
.\.venv\Scripts\alembic upgrade head
$env:CAREEROPS_RUN_INTEGRATION='1'
.\.venv\Scripts\python -m pytest tests/integration
Remove-Item Env:CAREEROPS_RUN_INTEGRATION
```

Recover stale or undispatched Analysis Runs:

```powershell
.\.venv\Scripts\python -m careerops.workers.analysis_recovery
```

The fake matcher is constructed directly by the analysis worker actor. Do not set a
live-provider flag for these checks.

## What You Must Understand

Level 1:

- `202 Accepted` means PostgreSQL contains durable work; it does not mean matching
  has completed.
- The fingerprint binds the run to both parsed requirements and the experience
  versions accepted at submission. Changed input fails explicitly instead of being
  processed silently.
- The idempotency key is the request identity. A database unique index makes
  concurrent retries with the same key converge. Different keys remain distinct
  requests even if their current inputs happen to match.
- At-least-once delivery is safe only because claiming is a conditional database
  state transition.
- Output coverage validation, citation validation, and database constraints protect
  different integrity boundaries.
- The succeeded transition and all verdict rows must be one transaction.

Level 2:

- Retrieval scoring is deterministic: exact skill matches dominate token overlap,
  and UUID ordering breaks ties.
- The matcher receives typed candidate sets and cannot choose an arbitrary source
  through normal code paths.
- The fake matcher never uses the Groq parser factory. It is deterministic boundary
  infrastructure, not a model-quality substitute.
- Recovery increments `attempt`, clears stale execution metadata, and rebuilds Redis
  delivery from PostgreSQL.

## Knowledge Check

1. Why does Analysis Run submission require an explicit `parse_run_id`?
2. Why must two accepted requests with different idempotency keys not be temporarily
   merged unless both keys are durably bound to the shared run?
3. Why does the worker commit `running` before matching?
4. Why should an experience edit produce `ANALYSIS_INPUT_CHANGED` instead of using
   the new text?
5. Why is malformed requirement coverage a failed run, while an invented evidence
   citation becomes `insufficient_evidence`?
6. What does the database unique verdict index protect that Python validation alone
   cannot?
7. What new components and measurements are required before replacing lexical
   retrieval with pgvector-backed hybrid retrieval?
