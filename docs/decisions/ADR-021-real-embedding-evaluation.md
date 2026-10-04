# ADR-021: Development-Only Real Embedding Evaluation

## Status

Accepted for P1-3a; its production-isolation restriction is superseded by ADR-023

## Context

The reviewed retrieval v2 development split records the unchanged lexical Top-5
baseline, while the holdout remains sealed. The Experience embedding lifecycle has
durable fake-only execution, but those hash-derived vectors carry no semantic
quality meaning. A real-provider experiment must measure vector and hybrid ranking
without changing Analysis Runs, production workers, database schema, or public APIs.

The experiment also needs a strict privacy and quota boundary. Gemini free-tier
traffic may be used by the provider to improve its products, so only the checked-in
synthetic corpus and development queries may leave the machine.

## Decision

Use `gemini-embedding-2` through an evaluation-only `httpx` adapter. Do not connect
the adapter to the production embedding worker. Keep the real provider disabled
unless all of these are true:

- `--provider gemini` is explicit;
- `CAREEROPS_RUN_EMBEDDING_EVAL=1` is set;
- `CAREEROPS_GEMINI_API_KEY` is present.

The first authorized run permits at most 40 synthetic Experience documents and 40
development queries. Documents and queries are separate synchronous batches with
one HTTP attempt each. Holdout input count must remain zero. Current account limits
must be checked in Google AI Studio before running; the code does not assume a
stable free-tier quota.

Request exactly 1536 dimensions. Use asymmetric, versioned text inputs:

```text
gemini-embedding-2-search-query-v1
task: search result | query: {requirement text}

gemini-embedding-2-search-document-v1
title: {title} | text: {canonical kind/description/skills/outcome JSON}
```

Do not send profile IDs, relevance labels, hard negatives, query tags, real resumes,
real job descriptions, or personal Experience data. The input hash binds role,
input version, and rendered text. Identical hashes are embedded once and fanned out.

Validate response count, model identity, exactly 1536 values, finite values, and a
non-zero norm before caching. Cache the vectors with model, dimension, input and
dataset hashes so ranking is reproducible even if the provider's stable model alias
later changes. A successful document batch may remain in an incomplete cache if the
query batch fails. No comparison report is written until the cache is complete.

Vector ranking uses cosine similarity rounded to 12 decimal places, then Experience
UUID ascending as the tie-break. Each query sees only its profile's Experiences.

Hybrid ranking uses weighted reciprocal rank fusion:

```text
alpha / (60 + lexical_rank) + (1 - alpha) / (60 + vector_rank)
```

Tune only on development with `alpha` in `0.25, 0.50, 0.75` and cosine thresholds
from `-0.20` through `0.90` in increments of `0.05`. First require negative
accuracy@5 at least equal to the lexical development baseline. Then maximize
Recall@5, Hit@5, MRR@5, Precision@5, negative accuracy@5, threshold, and finally
proximity to equal weights, in that order.

Report the existing fixed-denominator Precision@5, Recall@1/3/5, Hit@1/3/5,
MRR@5, negative accuracy@5, and mean returned candidates. Recompute lexical results
in memory and require exact agreement with the immutable saved lexical v2 baseline.

The holdout may be considered for a separately authorized one-time run only if the
selected development hybrid has Recall@5, negative accuracy@5, Hit@5, and MRR@5 no
worse than lexical, with at least one strict improvement. The same dominance rule is
the pre-registered holdout success criterion. A failed criterion is an experiment
result, not permission to tune against and rerun the holdout.

## Failure And Recovery Contract

- Missing opt-in or key fails before network access.
- HTTP 400 and authentication/authorization failures are terminal.
- Network failures, 408, 429, and selected 5xx failures are classified as
  recoverable, but the first authorized run still uses one attempt.
- Response shape, count, dimension, finite-number, and zero-norm failures invalidate
  the whole current batch.
- A validated earlier batch may be reused by a later separately authorized run;
  only missing input hashes are submitted.
- An incomplete cache records the last stable error code. It cannot produce a
  comparison artifact.
- Comparison output refuses overwrite, and the lexical baseline is read-only.

## Alternatives Considered

- Add the Google Gen AI SDK: rejected because existing `httpx` is sufficient and
  direct REST keeps retries and request attempts within the explicit budget.
- Connect Gemini to the production embedding worker: rejected because this stage
  evaluates quality without changing production lifecycle or provider behavior.
- Compare raw lexical and cosine scores directly: rejected because their scales are
  unrelated; rank fusion has a clearer deterministic contract.
- Run holdout together with development: rejected because provider and hybrid
  choices must be frozen before holdout access.
- Add pgvector or HNSW: rejected because the 10-Experience profile corpora need
  exact ranking, not an approximate-index variable.

## Consequences

The project can measure one real semantic embedding model while keeping default
tests offline, deterministic, and free. Raw vector caches add a larger evidence
artifact when a real run is eventually authorized. Provider aliases and synthetic,
single-reviewer data limit the strength of any quality claim.

No production retrieval, API, authorization, schema, migration, Redis, or worker
contract changes in this stage.

## Verification Or Evidence

- Unit tests cover input formatting, opt-in, provider request/usage parsing, error
  classification, dimensions, finite values, cosine ranking, metric behavior,
  immutable output, partial-batch recovery, and holdout refusal.
- A deterministic fake evaluation provider exercises the complete cache and report
  path without network access.
- Strict mypy, Ruff, import-linter, pytest, pip check, and diff checks remain gates.
- The authorized 2026-10-01 development run completed with 80 unique synthetic
  inputs, two single-attempt requests, 1536 validated dimensions, and zero holdout
  inputs. The saved evidence is documented in
  `docs/metrics/2026-10-01-gemini-embedding-2-development.md`.
- The selected vector threshold is `0.65`; the selected hybrid uses threshold
  `0.65` and lexical weight `0.50`. Both passed the pre-registered development gate.

## Revisit If

- A provider exposes a pinned immutable model version.
- Development results justify a separately approved holdout run.
- Production vector retrieval is proposed after the comparison.
- A second provider, asynchronous Batch API, ANN index, or paid traffic becomes an
  explicit requirement.
