# ADR-026: Groq Evidence Matcher Development Integration

## Status

Accepted; bounded recovery completed all 12 development cases

## Context

ADR-024 defines the provider-neutral matcher contract and ADR-025 freezes the
synthetic evaluation data. P1-5c needs to test a real structured-output model
without changing the worker, public API, database, frozen retrieval parameters,
or sealed matcher holdout.

## Decision

Use the existing Groq OpenAI-compatible HTTP capability with
`openai/gpt-oss-20b`. Keep the matcher prompt, provider-facing schema, and parser
independent from the Job requirement parser. A small shared transport owns only
authentication, timeout, retry delay, HTTP status classification, and request
counting.

The provider-facing matcher schema uses Groq strict JSON Schema and requires an
explicit nullable `evidence` field. The adapter normalizes that provider shape
into the stricter internal discriminated schema, which still rejects evidence on
gap verdicts and missing evidence on positive verdicts. Programmatic ownership,
candidate, version, source, and exact-quote validation remain downstream of the
adapter and cannot be bypassed by schema compliance or confidence.

Real development execution requires both the dedicated Groq runner and the
invocation-local `CAREEROPS_RUN_MATCHER_EVAL=1` opt-in. The model, prompt, schema,
dataset hashes, 800-token output ceiling, one attempt per case, and maximum 12
provider attempts are fixed for this run. The runner refuses existing output and
rejects the holdout before any provider call.

The authorized 2026-10-04 run used all 12 allowed attempts. Six cases completed
and six returned `provider_rate_limited`. Preserve that partial report as evidence;
do not overwrite it, silently retry, tune against failed cases, or treat partial
quality metrics as a complete development result. A recovery run must be separately
authorized and write a new artifact. The implemented recovery path hash-validates
the prior report, calls only its six failed case IDs, spaces calls by at least 11
seconds, and merges results without recalling successful cases.

The confirmed cause is the model's 8K tokens-per-minute rolling limit, not daily
or monthly exhaustion. The runner sent its requests in about nine seconds. The
first six completed cases reported 6,567 input and 1,081 output tokens, totaling
7,648 tokens before the seventh request entered the same rolling minute. Groq then
rate-limited cases 7 through 12. The account console showed about 8.2K tokens for
the day, far below the 200K tokens-per-day allowance, which is consistent with a
short TPM spike. Recovery therefore paces calls instead of changing model, prompt,
schema, labels, or frozen retrieval parameters.

The separately authorized recovery then retried only cases 7 through 12 with at
least 11 seconds between request starts. All six completed with no provider or
output failure. The new immutable report hash-links the prior artifact, records six
new and 18 cumulative attempts, and preserves the first six results unchanged.
The complete development metrics are not strong enough to freeze for holdout, so
holdout remains sealed while prompt/verdict policy work continues on development.

## Alternatives Considered

- Add a second provider or SDK: rejected because the existing HTTP dependency and
  Groq configuration are sufficient.
- Reuse the requirement parser schema or prompt: rejected because extraction and
  evidence judgment have different contracts and failure semantics.
- Fall back to the fake matcher after a real failure: rejected because it would
  hide provider unavailability under the real run identity.
- Retry 429 responses beyond the 12-call budget: rejected because it would exceed
  the announced invocation budget.
- Treat the failure as daily-quota exhaustion: rejected because the token totals,
  request timing, and provider console identify the rolling 8K TPM window.
- Overwrite the partial report after recovery: rejected because failed runs are
  operational evidence and historical metrics must remain immutable.

## Consequences

The repository now has a tested real matcher adapter, bounded development runner,
and verified recovery path, but the production worker remains fake-backed. The
complete development result is evidence for further prompt/model work, not
authorization for matcher holdout or worker integration.

## Verification Or Evidence

- HTTP mock tests cover minimal input, strict schema, valid positive/gap output,
  invalid JSON/schema, timeout, 401, 429, 5xx, and request counting.
- Runner tests cover explicit opt-in, missing credentials, the 12-attempt budget,
  immutable output, paced six-case recovery, prior-result preservation, and
  zero-call holdout refusal.
- `docs/metrics/2026-10-04-groq-evidence-matcher-development.json` preserves every
  case result, token count, failure category, hash, model, prompt, and schema.
- Real-provider requests: 12 development attempts; matcher holdout requests: 0.
- Authorized recovery: 6 additional development attempts, zero failures, zero
  holdout attempts, and 18 cumulative development attempts.

## Revisit If

- A recovery run completes the six rate-limited cases.
- The selected model, prompt, schema, retry policy, or request pacing changes.
- P1-5e connects a real matcher to the worker.

## 2026-10-04 Evaluation Update

ADR-027 corrects the evaluator without changing the saved provider output. The
complete recovery report was replayed offline with zero requests. Under rubric
v2, matcher-only verdict accuracy is `7/12` (`0.5833`), all six positive outputs
have acceptable grounded evidence, and canonical exact agreement is `0.0`. The
new development labels are pending author review, so no further provider run is
authorized.

Prompt v2 was subsequently implemented under ADR-027. The existing Groq reports
remain prompt-v1 evidence and are never relabeled as v2 output. The next run must
start a new immutable report after label/gate approval; resuming a prompt-v1
report is rejected by prompt and dataset provenance checks.

The separately authorized prompt-v2 run completed 12 paced attempts without 429
or provider failure. One response was `invalid_schema`, and the frozen quality
gates did not pass. This confirms pacing recovery but does not authorize holdout
or production integration.
