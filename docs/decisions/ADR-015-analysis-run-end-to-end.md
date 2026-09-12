# ADR-015: Analysis Run End-To-End Workflow

## Status

Accepted

## Context

ADR-014 established the persistence and validation boundary for evidence matches,
but users still could not submit, execute, or query an analysis. The next slice
must connect the public resource contract, deterministic retrieval, a fake matcher,
worker execution, validation, atomic completion, and recovery without introducing
another live provider variable.

An analysis also depends on two independently changing inputs: one successful parse
run and the current active experience library. Processing stale experience content
would make a stored citation disagree with the fingerprint accepted by the API.

## Decision

Expose nested analysis resources:

```text
POST /api/v1/jobs/{job_id}/analysis-runs
GET /api/v1/jobs/{job_id}/analysis-runs/{analysis_run_id}
```

POST requires `Idempotency-Key`, returns `202 Accepted`, and requires an explicit
successful `parse_run_id` in the body. It never selects an implicit latest parse
run. The input fingerprint includes the parse run ID, parse input fingerprint,
analysis prompt version, and every active experience's ID, version, and content
hash in stable order.

The idempotency key is the request identity. Concurrent submissions with the same
key converge on one run through a unique database index. Different keys represent
different requests even when their input fingerprints match. Input-level
coalescing is not performed because returning one shared run without durably
binding every accepted key would make later replays create unexpected new runs.

The API commits a queued row before dispatching only the analysis run ID through
Dramatiq and Redis. Conditional `queued -> running` claiming makes duplicate queue
messages harmless. PostgreSQL remains the durable task source, and a separate
recovery command requeues stale running analysis runs and redispatches queued rows.

The first retriever is pure and deterministic. For each requirement it scores
owned active experiences using exact normalized-skill matches plus lexical token
overlap, orders equal scores by experience ID, and returns at most five candidates.
Changes to retrieval or fake-matching semantics must bump the analysis prompt
version so old and new fingerprints cannot be mistaken for equivalent input.
The worker uses only `FakeEvidenceMatcher`; analysis execution cannot select or call
Groq in this slice. The fake emits deterministic, source-grounded proposals and is
test infrastructure, not a quality claim.

Before matching, the worker reloads the parse fingerprint and active experience
state. If the recomputed fingerprint differs, the run fails with
`ANALYSIS_INPUT_CHANGED`. Full experience snapshots are deferred; succeeded results
retain the cited quote and experience version, but do not reconstruct every field of
an older experience.

Matcher output must contain exactly one proposal for every requirement, with no
duplicates or foreign requirement IDs. Invalid output fails the run. Structurally
valid positive proposals still pass through ownership, candidate-membership,
version, and quote validation. Invalid positive claims are downgraded to
`insufficient_evidence`. A unique database index prevents more than one evidence
row for the same analysis run and requirement. All evidence rows and the succeeded
transition are committed atomically.

## Alternatives Considered

- Infer the latest successful parse run: rejected because the client and historical
  result would not explicitly identify the analyzed parse output.
- Use pgvector immediately: deferred so lifecycle, idempotency, recovery, and
  evidence integrity can be verified without embedding generation or retrieval
  quality variables.
- Snapshot complete experiences at submission: stronger historical reconstruction,
  but adds another table and write path. Fingerprint-and-fail is sufficient for this
  MVP slice and keeps ADR-014's known limitation explicit.
- Let missing or duplicate matcher results become gaps: rejected because malformed
  producer output should be distinguishable from a genuine lack of evidence.
- Allow multiple supporting experiences per requirement: deferred because the
  current product contract is one verdict and at most one cited experience.
- Deduplicate active runs by input fingerprint across different idempotency keys:
  rejected because a second accepted key would need a durable alias to the shared
  run. An alias table adds transaction and lifecycle complexity without an MVP need.

## Consequences

The user can now submit and poll an evidence analysis without API latency depending
on a matcher or provider. Runs are reproducible against an explicit parse result and
experience-library state, and retries of the same request converge in PostgreSQL.
Callers that intentionally send different idempotency keys create distinct runs.

Experience edits between submission and execution require a new analysis rather
than silently analyzing different input. Deterministic lexical retrieval is easy to
test and explain, but no retrieval-quality claim is made. A later retrieval-quality
milestone can add embedding generation, pgvector indexing, hybrid ranking, and a
versioned evaluation set without changing the run lifecycle or integrity boundary.

## Verification Or Evidence

- Unit tests cover fingerprinting, preconditions, dispatch failure, deterministic
  retrieval, fake matching, duplicate execution, changed inputs, malformed matcher
  output, claim downgrading, and recovery.
- PostgreSQL integration covers API submission and replay, worker completion, result
  query, cross-user hiding, unique verdict enforcement, same-key concurrency, and
  distinct-key creation.
- Redis integration verifies that dispatch contains only the analysis run ID.
- Alembic upgrade and downgrade verify the unique verdict index migration.
- Default pytest, `mypy --strict`, Ruff, and import-linter remain required gates.

No live Groq request, retrieval-quality metric, throughput metric, or latency
benchmark is part of this decision.

## Revisit If

- Historical analysis must reconstruct complete prior experience content.
- Evaluation shows lexical Top-5 retrieval misses useful evidence.
- Multiple evidence citations per requirement become a product requirement.
- Operational evidence justifies a transactional outbox instead of explicit
  redispatch and recovery.
