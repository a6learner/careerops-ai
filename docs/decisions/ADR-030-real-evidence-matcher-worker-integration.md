# ADR-030: Real Evidence Matcher Worker Integration

## Status

Accepted

## Context

The one-time prompt-v4 holdout passed every frozen evidence-integrity safety
gate, so a real matcher may enter the Analysis worker path. The API must still
never call a provider, fake execution must remain the default, and a queued run
must not silently change provider identity when process configuration changes.

## Decision

New Analysis Runs bind the matcher model into the existing pipeline version and
the existing `analysis_runs.model_name` column at submission time. No migration
or public API shape changes are required. The worker claims that durable work
item and resolves an adapter from its persisted model and prompt, rather than
from a mutable global provider choice.

The default is `CAREEROPS_EVIDENCE_MATCHER_PROVIDER=fake`. A Groq-bound run uses
only frozen prompt v4, schema v1, and `openai/gpt-oss-20b`. Actual worker network
access additionally requires the invocation-local process environment variable
`CAREEROPS_RUN_REAL_MATCHER_WORKER=1` and a configured key. The live flag is read
from `os.environ`, so a checked-in setting or `.env` value cannot authorize the
call by itself.

The worker performs one HTTP attempt. Timeout, 429, 5xx, disabled,
misconfigured, transport, invalid JSON, invalid schema, and invalid contract
outcomes become specific durable Analysis Run failures. There is no fake
fallback. Invalid-output logs record only safe field diagnostics, response hash,
response byte count, run/attempt identity, and model; raw provider text is not
logged or persisted.

The existing transaction validates every positive against user ownership,
Top-5 candidacy, Experience version, source field, and exact quote before atomic
persistence. Database constraints remain the final structural guard. Adapter
model output must also match the durable model binding.

Stale-running recovery may repeat an external call whose outcome was lost, but
incremented attempt fencing prevents the stale worker from committing. A normal
provider or output failure is terminal and visible; it is not automatically
retried or converted to a gap. Failed work can only be resubmitted through a new
explicit Analysis Run workflow.

## Alternatives Considered

- Resolve the matcher from current worker settings only: rejected because a
  restart could silently change an already queued run.
- Fall back to fake on provider failure: rejected because fake semantic output
  would be indistinguishable from real evidence matching.
- Reuse parser provider selection: rejected because parser and matcher have
  independent prompts, schemas, evaluation histories, and rollout authority.
- Add new provider-binding columns: rejected because the existing model and
  pipeline fields can represent the frozen identity without a migration.
- Add automatic retry or process-wide TPM scheduling now: rejected. One attempt
  keeps failure semantics clear; fleet-wide rate smoothing needs a separately
  designed durable coordinator.

## Consequences

Fake-backed CI and local workers remain deterministic. Real calls require two
separate choices: bind newly submitted runs to Groq and authorize the worker
process that may execute them. Operators must not leave an unauthorized worker
competing for a queue containing Groq-bound runs, because it will correctly
claim and fail them as disabled.

The integration preserves API, database, authorization, retrieval, and result
contracts. The system does not claim TPM smoothing or exactly-once external
effects.

## Verification Or Evidence

Focused tests cover fake defaults, `.env` non-authorization, missing keys,
unapproved model/prompt identity, durable fake binding across configuration
changes, one-attempt Groq construction, durable model mismatch, output-model
mismatch, specific failure mapping, safe invalid-output diagnostics, and a
mocked Groq execution through the Analysis worker service boundary.

PostgreSQL integration verifies durable model/pipeline binding. A real Dramatiq
E2E forces fake parser, matcher, and embedding providers in both processes and
confirms the worker completes an Analysis Run without network access. See
`docs/metrics/2026-10-06-real-evidence-matcher-worker-integration-test-record.md`.
