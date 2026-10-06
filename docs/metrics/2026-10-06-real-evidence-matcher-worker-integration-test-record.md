# Real Evidence Matcher Worker Integration Test Record

## Scope

This record covers P1-5e integration of the frozen real matcher behind the
Analysis worker adapter boundary. It does not measure matcher semantic quality;
that evidence is in the completed development and holdout reports. No provider
request was made during this verification.

## Behavior Verified

- matcher provider selection is independent from requirement parsing;
- fake remains the default for API submission, CI, and workers;
- new runs durably bind matcher model and prompt/schema/retrieval pipeline;
- a durable fake run stays fake after configuration changes;
- Groq requires prompt v4, `openai/gpt-oss-20b`, a key, and the process-only
  `CAREEROPS_RUN_REAL_MATCHER_WORKER=1` gate;
- `.env` alone cannot enable a real worker call;
- worker-side Groq uses one HTTP attempt and never falls back to fake;
- disabled, misconfigured, timeout, 429, 5xx, request, invalid JSON, invalid
  schema, and invalid contract outcomes map to specific durable error codes;
- invalid-output token counts persist, while safe response hash/size and field
  diagnostics are logged without raw response content;
- durable pipeline/model mismatch and provider output-model mismatch are fenced;
- positive evidence still passes ownership, candidate, Experience version,
  source, quote, and atomic persistence validation;
- Analysis attempt fencing and stale-running recovery semantics remain intact.

## Verification

Run on 2026-10-06 from branch `codex/p1-3b-embedding-holdout`, based on
`6041cf378004dc65c2634c666194a61465a565ab` with uncommitted P1-5 changes.

- 99 focused matcher and Analysis unit tests passed.
- 2 PostgreSQL Analysis Run integration tests passed.
- 1 real Dramatiq API-to-worker-to-PostgreSQL E2E passed.
- `mypy --strict` passed across 119 source files.
- Ruff passed.
- both import-boundary contracts passed across 119 files and 357 dependencies.
- `git diff --check` passed.

The first worker-E2E invocation intentionally stopped before setup because the
developer `.env` selected the Groq parser. No provider request occurred. The
successful run explicitly forced parser, matcher, and embedding providers to
fake in both the test process and worker container, and removed the live matcher
gate. This confirms the default offline safety boundary rather than relying on
ambient configuration.

## Data Model And API Impact

No migration and no public API shape change were required. Existing
`analysis_runs.model_name`, `prompt_version`, attempt, error, latency, and token
fields carry the durable binding and failure evidence.

## Limitations

The Groq worker path was tested through a mocked HTTP transport, not another live
provider call. The project does not claim process-wide TPM smoothing or
exactly-once external effects. A crash after Groq receives a request but before
local completion may lead stale recovery to repeat the external call; attempt
fencing prevents the stale worker from persisting afterward.
