# ADR-020: Retrieval Evaluation V2 And Holdout Policy

## Status

Accepted; labels frozen by the project author on 2026-09-21

## Context

ADR-019 created a reproducible lexical baseline, but its 20-Experience and 27-query
synthetic development set is too small and too easy to justify selecting a semantic
or hybrid retriever. It also uses binary relevance without recording whether one
Experience fully or partially supports a compound requirement.

The next evaluation must become harder without leaking holdout failures into later
embedding-provider choice, hybrid weighting, or retrieval tuning.

## Decision

Create retrieval evaluation v2 with four synthetic candidate profiles. Each profile
owns ten Experiences, for 40 Experiences total. Queries retrieve only from their
profile, mirroring the production user boundary without pretending one student owns
all 40 records.

Split 60 queries before evaluation:

- 40 development queries for implementation feedback and tuning;
- 20 frozen holdout queries reserved for the final lexical, vector, and hybrid
  comparison.

The dataset must contain exactly 15 zero-relevance queries, with ten in development
and five in holdout. It must also meet the checked quotas for semantic paraphrases,
cross-language cases, multiple relevant Experiences, compound requirements, and
hard negatives.

Each relevant label records an Experience ID, `full` or `partial` support, an exact
grounded quote, and a rationale. Both support levels count as relevant for candidate
retrieval metrics because the downstream matcher may legitimately return either
`matched` or `partial`. Hard-negative IDs cannot also be labeled relevant.
An optional hard-negative rationale documents subtle boundaries, such as synchronous
request idempotency versus duplicate asynchronous delivery.

The project author reviews every Experience, query, label, quote, rationale, and
negative case. Approval produces a manifest with SHA-256 hashes for the corpus and
both query files. The development evaluator refuses to run unless the manifest is
approved and its hashes match.

Report the following on positive queries:

- Recall@1, Recall@3, and Recall@5;
- Precision@5 using a fixed denominator of five candidate slots;
- Hit@1, Hit@3, and Hit@5;
- MRR@5 using zero when no relevant result appears in the Top-5.

Report negative accuracy separately on zero-relevance queries. Also record the mean
number of returned candidates to make abstention behavior visible.

Only the reviewed development split receives a lexical v2 baseline in this stage.
The CLI rejects holdout evaluation. Holdout is run once only after lexical, vector,
and hybrid candidates and parameters are frozen. Seeing holdout results does not
authorize tuning and rerunning against the same split.

No real provider, pgvector retrieval, production Analysis Run change, database
migration, or public API change belongs in this stage.

## Alternatives Considered

- One synthetic profile with 40 Experiences: rejected as unrealistic for the MVP
  user and less representative of per-user retrieval boundaries.
- Binary labels only: rejected because compound requirements need auditable partial
  support without treating a mere technology mention as relevant.
- Divide Precision@5 by returned candidates: rejected because systems could improve
  precision by returning very few candidates. Recall, Hit, and returned-count
  reporting expose the fixed-budget trade-off.
- Run the lexical holdout baseline immediately: rejected because its failure cases
  could influence later provider choice or hybrid tuning.
- Use the fake embedding vectors: rejected because deterministic hashes do not carry
  semantic meaning.

## Consequences

Future retrieval implementations can be compared on identical reviewed labels and
metric definitions. The manifest makes post-review label or corpus edits visible.
Development results remain available for iteration while the holdout stays sealed.

The author must perform a real manual review before any v2 quality number is saved.
Synthetic data and a single reviewer still limit external validity, so final scores
must retain those limitations.

## Verification Or Evidence

- Schema tests cover profile isolation, exact quote grounding, support levels,
  negative rationales, and immutable review hashes.
- Formula tests cover fixed-cutoff Precision, Recall, Hit, MRR, and negative
  abstention.
- Dataset tests enforce all size and difficulty quotas without running retrieval.
- CLI tests require an approved manifest, refuse overwrite, and reject holdout.
- Default pytest, strict mypy, Ruff, import-linter, pip check, and diff checks remain
  required. Real model calls remain zero.
- The reviewed lexical development baseline is preserved in
  `docs/metrics/2026-09-21-lexical-retrieval-v2-development.json`; the holdout was
  not executed.

## Revisit If

- Human review shows that binary retrieval relevance cannot safely combine full and
  partial labels.
- More than one reviewer becomes available and disagreement measurement is useful.
- The product changes its Top-5 candidate contract.
- A new holdout is required after the current holdout has influenced tuning.
