# ADR-019: Evidence Retrieval Evaluation Baseline

## Status

Accepted

## Context

Analysis Runs currently use deterministic exact-skill and lexical-overlap ranking
to select at most five Experience candidates for each requirement. Experience
embedding lifecycle correctness now exists, but the fake vectors have no semantic
quality meaning. Replacing the production retriever before freezing labels and
metrics would make later comparisons impossible to interpret.

Retrieval quality is separate from evidence-matcher quality. This stage needs to
measure whether relevant Experiences enter the candidate set without introducing a
real provider, pgvector query, or matcher variable.

## Decision

Create a versioned synthetic development set with one shared Experience corpus and
binary relevance labels for each requirement. A requirement may have multiple
relevant Experiences or no relevant Experience. Labels are stable Experience IDs,
not rank positions.

Evaluate the existing `lexical-skill-v1` retriever without changing its production
behavior. Save the full ranked Top-5 output for every query so aggregate numbers
remain traceable to individual labels.

For queries with at least one relevant Experience, report macro-averaged
`Recall@1`, `Recall@3`, `Recall@5`, and `MRR@5`:

- Recall@K is the number of relevant Experience IDs in the first K results divided
  by the total relevant IDs for that query.
- MRR@5 uses the reciprocal rank of the first relevant result and assigns zero when
  no relevant result appears in the first five.

Recall and MRR are undefined for queries with no relevant Experience. Report those
queries separately as `no_relevant_returned_accuracy_at_5`, which is successful
only when the retriever returns no candidate.

The evaluator is deterministic, validates dataset identity and references, records
the dataset hash and Git revision, and refuses to overwrite an existing report.
The checked-in set is a development set, not a holdout or production sample.

A real embedding provider is explicitly deferred. The next provider or hybrid
retrieval stage must reuse the frozen dataset and metric definitions before any
production retrieval switch is considered.

## Alternatives Considered

- Evaluate fake embeddings: rejected because their deterministic hash vectors do
  not encode semantic similarity.
- Report only hit rate: rejected because it hides missing relevant Experiences when
  a requirement has multiple valid sources.
- Include zero-relevance queries in Recall or MRR with an invented denominator:
  rejected because that changes the meaning of those metrics.
- Change Analysis Run retrieval in the same stage: rejected because baseline
  measurement should not alter the behavior being measured.
- Start with a live provider: deferred so dataset and scoring defects can be found
  without network, cost, or model-version variables.

## Consequences

The project now has a reproducible lexical baseline and concrete failure cases for
future vector or hybrid ranking. The result can be regenerated offline at zero
provider cost.

The small synthetic set was authored for development, so its scores must not be
described as production accuracy or generalization. Binary labels also do not
express degrees of relevance. A later holdout set or graded relevance metric would
be a separate decision.

No API, database schema, worker lifecycle, Analysis Run fingerprint, or production
retrieval behavior changes in this stage.

## Verification Or Evidence

- Dataset validation tests cover duplicate and unknown identifiers.
- Metric tests cover multiple relevant Experiences, first-relevant rank, empty
  rankings, and noisy negative-query results.
- CLI tests verify immutable output behavior.
- The raw ranked output and aggregate baseline are stored in
  `docs/metrics/2026-09-20-lexical-retrieval-baseline.json`.
- Default pytest, strict mypy, Ruff, import-linter, pip check, and diff checks are
  required. Real model requests remain zero.

## Revisit If

- A real embedding provider is selected and produces semantically meaningful
  versioned vectors.
- A frozen holdout set, human disagreement measurement, or graded relevance is
  needed for stronger quality claims.
- Product requirements change from one candidate corpus per user or from Top-5
  candidate generation.
