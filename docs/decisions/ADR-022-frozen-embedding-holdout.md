# ADR-022: Frozen One-Time Embedding Holdout

## Status

Accepted

## Context

P1-3a committed the reviewed synthetic development comparison at `0c6d9cd`.
Development selected a vector cosine threshold of `0.65` and a weighted-RRF hybrid
with threshold `0.65`, lexical weight `0.50`, vector weight `0.50`, and `k=60`.
Those choices and the success criterion must be immutable before any holdout ranking
is observed.

The development cache already contains validated `gemini-embedding-2` vectors for
all 40 synthetic Experiences. Re-embedding them would spend quota and could produce
a second corpus representation under the same mutable provider alias.

## Decision

Use an independent P1-3b holdout runner. It must verify all of these frozen inputs
before accepting a provider response:

- P1-3a commit: `0c6d9cd139ae05efa28aa038dc26fae912807d66`;
- normalized committed development comparison SHA-256:
  `19aa221b03b6795571407b680c5cadcaa5b1be80a6307253801f4dcee33f40b1`;
- development vector cache SHA-256:
  `8b07d9f80dc40d0fa744bab038034f39e4f6a4f9a69f2fe5b44f6419d82ad7b8`;
- corpus and development-query hashes from the approved review manifest;
- model `gemini-embedding-2`, 1536 dimensions, input versions, zero development
  holdout inputs, both development gates passing, and the fixed parameters above.

Normalize CRLF to LF only when hashing the text JSON report so the committed
artifact has one cross-platform identity. Keep the gzip cache hash byte-exact.

Reuse exactly 40 validated document vectors from P1-3a. Submit exactly 20 synthetic
holdout queries in one synchronous batch with one HTTP attempt. Require both the
ignored `.env` key and the invocation-only
`CAREEROPS_RUN_EMBEDDING_HOLDOUT=1` flag. This flag is separate from the development
flag so prior authorization cannot accidentally unlock holdout.

Do not expose a fake-provider CLI mode. Unit tests use development-derived toy
queries marked as holdout and never load the real holdout file. The real CLI has no
threshold, weight, grid, or provider arguments.

Evaluate lexical, vector, and hybrid rankings with the frozen settings. For vector
and hybrid separately, holdout success requires Recall@5, negative accuracy@5,
Hit@5, and MRR@5 all no worse than holdout lexical, with at least one strict
improvement. A failure is the final experimental result; it does not authorize
retuning or a second holdout run.

## Failure And Recovery Contract

- Missing opt-in or key fails before reading holdout inputs or making a request.
- A changed development artifact, cache, corpus, manifest, model, dimension, input
  version, parameter, or count fails before provider access.
- Authentication, invalid-request, response, dimension, and vector failures are
  terminal for the authorized attempt.
- Network, 408, 429, and selected 5xx failures are classified as recoverable, but
  the authorized run still performs no automatic retry.
- A failed query batch writes an incomplete cache with a stable failure code and no
  comparison report. A later retry requires separate authorization.
- A validated complete query cache may be reused to recover a local reporting
  failure without another provider call.
- Cache and comparison paths refuse incompatible identity or output overwrite.

## Alternatives Considered

- Re-embed corpus and holdout together: rejected because the validated corpus
  already exists and the mutable model alias could create an unnecessary second
  representation.
- Reuse the development runner with a split override: rejected because it contains
  parameter selection and should continue rejecting holdout.
- Add a fake CLI mode: rejected because it would make accidental real-holdout
  ranking observation too easy.
- Tune after seeing holdout: rejected because it converts holdout into development
  data and invalidates the one-time claim.

## Consequences

The real holdout call budget is reduced from 60 inputs to 20 and the development
selection path remains sealed from holdout. The result remains tied to a mutable
provider alias and a small synthetic, single-reviewer dataset. No production API,
worker, database, authorization, or retrieval behavior changes.

## Verification Or Evidence

- Unit tests verify frozen artifact identity, query-only input planning, one-batch
  fake-provider caching, fixed parameters, incomplete-cache recovery, output
  immutability, and distinct opt-in.
- Test source must not reference `holdout_queries.json`.
- Strict mypy, Ruff, pytest, import-linter, pip check, and secret checks remain
  required.
- No real holdout cache, ranking, or metrics artifact exists before separate live
  authorization.

## Revisit If

- P1-3a evidence is intentionally superseded before any holdout run.
- Google exposes a pinned immutable model version compatible with the saved vectors.
- A provider failure requires a separately authorized retry of the missing query
  batch.
