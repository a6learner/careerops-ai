# Metrics And Evidence

This directory stores measured evidence for claims made in the README, demo, resume bullets, interview notes, or project summaries.

## Rule

If a number was not measured and saved, do not use it as a claim.

Say `not measured` instead of inventing latency improvements, accuracy, recall, throughput, cost savings, reliability, coverage, cache hit rate, or task success rate.

## Metrics To Collect

Useful metrics for this project include:

- main read endpoint P50 and P95 latency
- before/after query plans for indexed endpoints
- async task success, retry, timeout, and permanent failure rates
- cache hit rate
- duplicate analysis requests blocked by idempotency controls
- unsupported positive claims blocked by validation and database constraints
- endpoint coverage by tests
- average analysis latency and estimated token cost

## Evidence Format

Prefer small, durable files:

- benchmark command and environment
- raw output or summarized table
- date measured
- git commit or branch
- dataset or fixture used
- interpretation and limitations

Do not overwrite old results when comparing performance. Add a new dated artifact so the improvement can be traced.

## Current Retrieval Evidence

- `2026-09-20-lexical-retrieval-baseline.md` explains the metric definitions,
  observed baseline, and limitations.
- `2026-09-20-lexical-retrieval-baseline.json` preserves the full ranked output.
- `2026-09-21-lexical-retrieval-v2-development.md` explains the reviewed,
  multi-profile development baseline and sealed-holdout boundary.
- `2026-09-21-lexical-retrieval-v2-development.json` preserves the full v2
  development ranking output and dataset hashes.
- `2026-10-01-gemini-embedding-2-development.md` explains the controlled real
  embedding comparison and its limitations.
- `2026-10-01-gemini-embedding-2-development-comparison.json` preserves every
  lexical, vector, and hybrid development ranking.
- `2026-10-01-gemini-embedding-2-development-vectors.json.gz` preserves the
  validated 1536-dimensional development vector cache.
- `2026-10-03-gemini-embedding-2-holdout.md` explains the authorized one-time
  holdout comparison and its limitations.
- `2026-10-03-gemini-embedding-2-holdout-comparison.json` preserves every frozen
  lexical, vector, and hybrid holdout ranking.
- `2026-10-03-gemini-embedding-2-holdout-queries.json.gz` preserves the validated
  query-only holdout vector cache.
- `2026-10-03-local-hybrid-retrieval-test-record.md` records the offline and local
  PostgreSQL verification for production-path hybrid retrieval integration.

## Current Matcher Evidence

- `2026-10-04-fake-evidence-matcher-development.md` explains the author-approved
  offline pipeline run and why fake scores are not semantic-quality evidence.
- `2026-10-04-fake-evidence-matcher-development.json` preserves every raw and
  validated development result plus the frozen dataset hashes.
- `2026-10-04-groq-evidence-matcher-development.md` explains the first bounded
  real-provider run, its partial result, and its rate-limit recovery boundary.
- `2026-10-04-groq-evidence-matcher-development.json` preserves all 12 case
  outcomes, including the six durable `provider_rate_limited` failures.
- `2026-10-04-groq-evidence-matcher-development-recovery.md` explains the paced,
  six-request recovery and the complete development metrics.
- `2026-10-04-groq-evidence-matcher-development-recovery.json` preserves the
  merged 12-case result and its prior-report provenance.
- `2026-10-04-groq-evidence-matcher-development-offline-rescore-v2.md` explains
  the zero-request rubric-v2 replay and separates model, retrieval, and canonical
  quote effects.
- `2026-10-04-groq-evidence-matcher-development-offline-rescore-v2.json`
  preserves the per-case v2 component metrics and source-report hash.
- `2026-10-04-groq-evidence-matcher-development-prompt-v2.md` records the first
  paced prompt-v2 development run, its gate failures, and zero holdout calls.
- `2026-10-04-groq-evidence-matcher-development-prompt-v2.json` preserves all 12
  prompt-v2 case outcomes, including one durable `invalid_schema` failure.
- `2026-10-04-groq-evidence-matcher-development-prompt-v2-coverage-v1.md`
  explains the zero-request three-class coverage rescore and proposed next gates.
- `2026-10-04-groq-evidence-matcher-development-prompt-v2-coverage-v1.json`
  preserves all denominators, failure policy, and directional error counts.
- `2026-10-05-groq-evidence-matcher-prompt-v3-v5-development.md` compares the
  bounded prompt iterations, selects v4 as the safest development candidate,
  and records the quality-gate stop before holdout or worker activation.
- `2026-10-05-evidence-matcher-prompt-v4-author-exception.md` records the
  author's post-measurement acceptance of the one conservative underclaim while
  preserving the original quality-gate failure.
- `2026-10-05-evidence-matcher-holdout-readiness.md` records the offline one-time
  runner verification, rubric-v2 holdout migration hash, and pre-execution
  boundary; it is not a holdout result and made no provider request.
- `2026-10-05-groq-evidence-matcher-holdout.md` records the authorized one-time
  holdout safety pass and the visible 6/8 matcher-only coverage limitation.
- `2026-10-05-groq-evidence-matcher-holdout.json` preserves the immutable raw
  holdout outcomes, denominators, token usage, and frozen gate decision.
- `2026-10-05-groq-evidence-matcher-holdout-checkpoint.json` preserves the
  at-most-once request ledger for all eight cases.
- `2026-10-06-real-evidence-matcher-worker-integration-test-record.md` records
  offline, PostgreSQL, and real-Dramatiq verification of the controlled worker
  integration; no provider request was made.
- `2026-10-06-analysis-admission-rate-limit-test-record.md` records offline,
  PostgreSQL, and direct Redis-container verification of per-user Analysis Run
  admission control, including the current host-port test limitation.
- `2026-10-06-analysis-run-observability-test-record.md` records JSON logging,
  Analysis correlation and recovery verification, plus the corrected worker-E2E
  provider-selection incident.
- `2026-10-06-analysis-run-lifecycle-constraint-test-record.md` records the
  populated- and empty-database migration checks plus direct PostgreSQL lifecycle
  rejection evidence.
- `2026-10-06-api-readiness-test-record.md` records the PostgreSQL-and-Redis
  readiness matrix, real 503 semantics, and local-container success path.
