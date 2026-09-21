# ADR-018: Version-Bound Experience Embedding Lifecycle

## Status

Accepted

## Context

Experiences already contain a nullable `vector(1536)` column, but no process
generates it or records which Experience version, content hash, model, and input
format produced it. A background result must not overwrite a newer user edit, and
Redis message loss or duplicate delivery must not lose or duplicate durable work.

This stage establishes lifecycle correctness before vector retrieval or a real
embedding provider adds quality and network variables.

## Decision

Keep the current usable vector and its provenance on `experiences`. Store durable
execution history in `experience_embedding_runs`, bound to Experience ID, version,
content hash, model name, and input version.

Experience create and update create a `queued` run in the same PostgreSQL
transaction as the business write. An update first supersedes an active older run,
then updates the Experience, clears prior vector provenance, and creates the new
run. Soft deletion supersedes active work and clears the derived vector.

Dispatch happens after commit and sends only the run ID through Dramatiq/Redis.
Dispatch failure does not turn a committed Experience write into an API failure;
the run remains queued for recovery.

Workers claim with a conditional `queued -> running` update. Completion is bound
to the claimed attempt as well as the target Experience version and content hash.
Recovery increments the attempt when requeueing stale work, so an older worker can
no longer complete after a newer attempt has claimed the run. An Experience edit
or deletion makes prior work `superseded`.

Embedding completion updates only derived columns. It does not increment the
Experience business version or change `content_hash` or `updated_at`.

Use a typed provider protocol and a deterministic 1536-dimensional fake provider.
No real embedding model or network call is configured. The input format is
versioned as `experience-embedding-input-v1`. Use the official Python `pgvector`
package for vector binding and future query operators.

Recovery reconciles active Experiences that lack a current target run, requeues
stale running work, and redispatches queued IDs. Provider and output failures are
terminal in this fake-only stage; bounded transient provider retry policy is
deferred until a real provider exists.

## Alternatives Considered

- Store only a status on `experiences`: rejected because it loses attempt and
  failure history and cannot identify stale worker results cleanly.
- Store every vector on the run: rejected because P1 retrieval needs one simple,
  authoritative current vector and does not need historical vector queries.
- Fail Experience writes after post-commit Redis failure: rejected because create
  has no request idempotency key and client retry could duplicate business data.
- Introduce real embeddings now: rejected because lifecycle and concurrency must
  be deterministic before measuring retrieval quality.
- Add a transactional outbox: deferred because PostgreSQL reconciliation and
  redispatch close the current single-user failure window with less machinery.

## Consequences

PostgreSQL can rebuild embedding delivery after Redis loss. Duplicate messages may
cause duplicate delivery, and stale recovery could eventually cause duplicate
provider computation, but database completion remains idempotent and version-safe.

The additional run table and provenance columns add schema and operational state.
Vector retrieval must later require matching content, model, and input provenance;
the existence of a non-null vector alone is not sufficient.

## Verification Or Evidence

- Unit tests cover deterministic input/output, dimension and finite-number
  validation, duplicate delivery, failure states, scheduling, and recovery counts.
- PostgreSQL integration covers vector round-trip, stale completion after an edit,
  concurrent claims, recovery attempt fencing, and reconciliation.
- Redis integration verifies that only a run ID is queued.
- Migration downgrade, upgrade, `alembic current`, and `alembic check` are required.
- Default checks make zero real-provider requests.

## Revisit If

- A real provider needs transient versus permanent retry classification.
- Retrieval evaluation justifies hybrid pgvector ranking and an ANN index.
- Historical vector reconstruction or multiple active models becomes a product
  requirement.
- Operational evidence justifies a transactional outbox or automatic scheduler.
