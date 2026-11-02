# ADR-048: Evidence Matcher Failure Diagnostics

## Status

Accepted by the author on 2026-11-01 (stage 1 of the matcher-reliability plan).
Implemented and verified locally with fake transports. Not yet re-measured
against a real provider.

## Context

The large_scale_v1 development evaluation
(`docs/metrics/2026-11-01-large-scale-eval-v1.md`) completed 59 of 150 real
analyses. The failures were 62 `MATCHER_OUTPUT_INVALID_CONTRACT`, 28
`MATCHER_PROVIDER_FAILED` and 1 `MATCHER_OUTPUT_INVALID_SCHEMA`. The record
could not prove their causes, for three reasons:

1. **Schema rejections looked like provider failures.**
   - When Groq's server-side JSON-schema check rejects the model's output, Groq
     answers HTTP 400 `json_validate_failed`.
   - Through OpenRouter, the same rejection arrives as HTTP 200 with
     `finish_reason: "error"` and `content: null` (`provider_probes.md`).
   - Both paths became `REQUEST_FAILED`, then `MATCHER_PROVIDER_FAILED`, which
     tells the user to retry a provider that was working.
2. **Contract failures kept nothing.** A run whose match list did not cover the
   requested requirements exactly stored no token counts and logged no reason.
   That hid whether the 800-token output cap was the cause.
3. **The frontend copy was wrong.** It told users that `INVALID_CONTRACT` meant
   "cited evidence that could not be verified". The contract check fails on
   requirement coverage (missing, extra or duplicate IDs) and on evidence-field
   shape. Quote verification happens later and never fails a run.

## Decision

- **Transport.** `GroqRequestError` keeps the provider's `error.code` from a
  non-2xx JSON body (`provider_error_code`). Status classification and retry
  behavior are unchanged, so the parser behaves as before.
- **Groq schema rejection.** In the matcher adapter, a Groq
  `json_validate_failed` error raises `MatcherOutputValidationError(INVALID_SCHEMA)`,
  stored as `MATCHER_OUTPUT_INVALID_SCHEMA`.
- **Aborted generation.** A 200 response whose `finish_reason` is `error` or
  `length` raises `INVALID_SCHEMA` and keeps the token counts. The diagnostic
  names the finish reason.
- **Null content with any other finish reason** stays `REQUEST_FAILED`.
- **Contract diagnostics.** A contract failure stores the output's token counts
  on the failed run. It also logs the diagnostic
  `expected=..;returned=..;missing=..;unknown=..;duplicates=..;invalid_shape=..`
  in the existing `evidence_matcher_output_rejected` event.
- **Frontend copy.** The `MATCHER_OUTPUT_INVALID_CONTRACT` message now says the
  matcher did not return one valid answer for every requirement.
- No new error codes, no migration (`analysis_runs.error_code` is free text), no
  prompt or model change.

## Alternatives considered

- **A new `MATCHER_OUTPUT_INCOMPLETE` code** for coverage failures. Rejected for
  now: it changes the public error enum, and the diagnostic already separates
  coverage from shape.
- **A failure-detail column on `analysis_runs`.** Rejected for this stage: it
  needs a migration. The structured log is enough to confirm the token-cap
  hypothesis; durable detail can be proposed later if it is needed.
- **Classifying OpenRouter `finish_reason: "error"` only when the message says
  "Parsing failed".** Rejected: matching provider prose is brittle.

## Consequences

- Runs that used to report `MATCHER_PROVIDER_FAILED` for a schema rejection now
  report `MATCHER_OUTPUT_INVALID_SCHEMA`. Counts from before and after this
  change are not directly comparable.
- **Risk:** OpenRouter can also report `finish_reason: "error"` for an upstream
  fault unrelated to the output. Such a fault is now labeled an output failure.
  large_scale_v1 saw only the schema-rejection case, but that is one probe, not
  a proof.
- Diagnostics live in worker logs, not the database. Logs must be kept (UTF-8,
  appended, one file per session) for any evaluation that relies on them.

## Verification or evidence

- `tests/test_groq_evidence_matcher.py`:
  - Groq 400 `json_validate_failed` gives `INVALID_SCHEMA`.
  - 200 with `finish_reason` `error` or `length` gives `INVALID_SCHEMA` with tokens.
  - Null content with `stop` gives `REQUEST_FAILED`.
  - A plain 400 still gives `REQUEST_FAILED`.
- `tests/test_analysis_run_execution.py`: omitted, duplicate and extra
  requirement IDs fail with stored tokens and the exact diagnostic.
- Gates on 2026-11-01:
  - `ruff check .` and `mypy --strict src` (145 files) clean.
  - `lint-imports` 2 contracts kept.
  - `pytest tests --ignore=tests/integration`: 457 passed.
  - Frontend `vitest` 43 passed; `tsc --noEmit` and `eslint` clean.
- Real-provider confirmation of the token-cap hypothesis: not measured yet. It
  is planned as a small dev-only re-run that needs separate author approval.
