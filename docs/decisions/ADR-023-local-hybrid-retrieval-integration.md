# ADR-023: Local Exact Hybrid Retrieval Integration

## Status

Accepted

## Context

The frozen Gemini evaluation and one-time holdout both justified the fixed
lexical/vector weighted-RRF configuration. Production Analysis Runs still used
lexical retrieval, while Experience vectors already had durable version, content,
model, input-version, and attempt provenance.

## Decision

Use exact PostgreSQL/pgvector cosine scoring inside the Analysis worker. Keep SQL
and authorization filters in a repository and keep provider calls, fallback, and
rank fusion in a typed retrieval service.

The frozen semantic space is `gemini-embedding-2`, 1536 dimensions, query input
version `gemini-embedding-2-search-query-v1`, and document input version
`gemini-embedding-2-search-document-v1`. Vector and hybrid thresholds are `0.65`;
lexical and vector weights are `0.50`; RRF uses `k=60`.

Lexical retrieval always sees all owned active Experiences. Vector retrieval sees
only rows owned by the same user whose content hash, model, document input version,
and embedding provenance match. It also requires `embedded_at` no later than the
Analysis Run creation time, so recovery cannot gain newly completed vectors.

When some valid vectors exist, fuse their ranking with lexical results. When none
exist, or query embedding fails validation or provider execution, complete the run
with lexical candidates. Do not block Analysis Runs on vector availability.

Use exact search because the expected corpus is at most about 40 Experiences. Do
not add ANN/HNSW. Keep the fake provider as the default for offline CI. Gemini
requires both explicit provider selection and invocation-local live opt-in.
The live opt-in is read directly from the worker process environment and is not a
Settings/`.env` field.

The existing Gemini HTTP adapter is shared by evaluation and worker execution;
evaluation-specific budgets, caches, and sealed-split rules remain in evaluation
code. Production and evaluation also use one pure weighted-RRF implementation so
ranking semantics cannot drift independently. The public API and database schema do
not change. The evidence matcher remains
fake in this stage so retrieval behavior is independently testable.

Analysis completion and failure are fenced by the claimed attempt. A recovered old
worker cannot persist after a newer attempt claims the run.

Embedding workers resolve providers from each durable run's model and document input
version, not from the current global provider selection. Analysis Runs bind their
retrieval space into the persisted pipeline version and input fingerprint. Disabled
or misconfigured Gemini query providers produce typed lexical fallback; document
embedding runs are claimed and persist a distinct terminal error.

## Alternatives Considered

- Require every vector before analysis: rejected because one failed embedding would
  make the whole user workflow unavailable.
- Fall back entirely when one vector is missing: rejected because valid semantic
  evidence can be used safely while lexical still covers the complete library.
- Add HNSW: rejected because it adds approximate-retrieval variables without a
  scale need.
- Add a real evidence matcher now: deferred to keep retrieval and verdict quality
  independently diagnosable.

## Consequences

Local Analysis Runs now exercise API-to-worker-to-pgvector hybrid retrieval while
retaining deterministic fallback and evidence validation. Partial vector coverage
can bias the semantic rank toward completed rows, so logs record eligible and total
counts and claims must not describe partial coverage as complete semantic indexing.

## Verification Or Evidence

Unit tests cover fixed RRF ordering and provider fallback. PostgreSQL integration
tests cover exact cosine scoring, ownership, provenance, and snapshot-time fencing.
Analysis integration tests cover recovery-attempt fencing. The default CI path uses
no network or paid provider. A separately gated worker E2E covers the real
API-to-Dramatiq-to-pgvector-to-persistence path with forced fake providers.

## Revisit If

- Measured corpus size or query plans justify ANN.
- Historical runs need persisted retrieval telemetry in the public API.
- A separately evaluated real evidence matcher is approved.
