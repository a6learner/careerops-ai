# 0032 Real Evidence Matcher Worker Integration

## What Changed

Analysis submission now durably binds a matcher model into the existing pipeline
identity. The worker resolves either the deterministic fake or the frozen Groq
adapter from that work item. Real network access requires a process-only live
gate and never falls back to fake.

## Why It Exists

A queue can outlive a deploy or configuration change. If the worker selected a
provider only from current settings, the same durable job could change meaning
after a restart. Binding model, prompt, schema, and retrieval space at submission
keeps recovery reproducible.

## Failure Modes It Prevents

- API latency or availability depending on a provider call.
- A queued fake job becoming real after configuration changes.
- A Groq failure being hidden behind plausible fake matches.
- Old prompt or model output entering the frozen production path.
- A provider returning a different model than the durable job requested.
- Malformed output becoming a normal evidence gap.
- A stale attempt committing after recovery incremented the attempt number.
- Raw synthetic or future user content leaking into invalid-output logs.

## How It Was Verified

Unit tests exercise resolver authorization, durable identity fencing, exact
failure codes, token accounting, safe diagnostic logging, and mocked Groq
execution without network access. PostgreSQL tests verify the persisted binding.
A real Dramatiq E2E runs with explicitly forced fake providers and completes the
full API-to-worker-to-database path.

## What You Must Understand

Level 1: provider selection and provider authorization are different. The API
binds intent; only the worker-side process gate permits the external effect.

Level 1: idempotent database completion is not exactly-once provider execution.
A crashed running attempt may have reached Groq; recovery can repeat that call,
but attempt fencing prevents stale database writes.

Level 1: quote grounding proves that cited text exists, not that it fully covers
the requirement. Verdict shape, candidate/version/ownership checks, grounding,
and database constraints protect different invariants.

Level 2: prompt v4 and `openai/gpt-oss-20b` are allowlisted in the resolver.
Invalid-output logs contain diagnostics and a hash, never raw response content.

## Knowledge Check

1. Why is the matcher model stored before the worker claims the job?
2. Why is a key in `.env` insufficient to authorize a real matcher call?
3. What happens to a 429, invalid JSON, or invalid schema result?
4. How can stale recovery repeat a provider call while still protecting the
   database from stale persistence?
5. Why are citation grounding and `partial -> matched` separate safety checks?
