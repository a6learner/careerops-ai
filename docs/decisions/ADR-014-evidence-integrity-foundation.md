# ADR-014: Evidence Integrity Foundation

## Status

Accepted

## Context

Requirement parsing produces claims about a job description, but it does not prove
that the candidate owns matching experience. Evidence matching therefore needs a
separate immutable run and a persisted verdict for every requirement. Model output
is untrusted: it may cite an unknown experience, another user's experience, a stale
version, a non-candidate experience, or text that does not occur in the source.

## Decision

Introduce `analysis_runs` and `evidence_matches` as the persistence foundation for
US-005 and US-006.

- Each analysis run references the exact successful parse run whose requirements
  are being analyzed.
- Application validation checks experience existence, ownership, candidate-set
  membership, current version, and a whitespace-normalized exact quote.
- Any invalid positive claim is stripped and downgraded to
  `insufficient_evidence`; the run records how many matches were downgraded.
- Both `matched` and `partial` are positive evidence verdicts. They require an
  experience ID, version, non-empty quote, and `quote_valid = true`.
- `missing` and `insufficient_evidence` cannot carry experience IDs, versions, or
  quotes.
- Completing a run and inserting all evidence rows uses one PostgreSQL transaction.
  If any evidence row violates a constraint, the run does not become succeeded.
- PostgreSQL enforces the timestamp and error-code shape of every Analysis Run
  lifecycle state. Direct writes cannot persist a queued run with timestamps, a
  running run with a finish time, or an invalid terminal state.
- Concurrent active analysis for the same job input is prevented by a partial
  unique index. Idempotency is scoped to user and job.

This slice intentionally does not add retrieval, an evidence-matching provider,
worker dispatch, or public endpoints. Those will build on this integrity boundary.

## Alternatives Considered

- Trust the model's `quote_valid` flag: rejected because the producer of a claim
  cannot also be its only verifier.
- Validate only in Python: rejected because application bugs and direct writes
  could persist structurally unsupported positive claims.
- Require evidence only for `matched`: rejected because `partial` still communicates
  that the user has some supporting experience.
- Add experience-version history in this slice: deferred to keep this change small.
  The stored quote and version identify the cited snapshot, but full historical
  source reconstruction needs a later snapshot/history decision.

## Consequences

- Invalid citations become visible gaps instead of disappearing or becoming claims.
- Database constraints provide a final structural backstop while application code
  performs semantic checks that SQL cannot reasonably express, such as substring
  grounding and candidate-set membership.
- Future worker code must validate before calling the result persistence service.
- The project still needs an explicit policy for reconstructing old experience
  versions after an experience is edited.

## Verification Or Evidence

- Unit tests cover valid evidence, unknown and cross-user IDs, stale versions,
  candidate-set violations, invalid quotes, and explicit gaps.
- Model metadata tests keep SQLAlchemy declarations aligned with the migration.
- PostgreSQL integration tests verify that an invalid positive row causes the run
  transition and all evidence writes to roll back together.
- Migration and PostgreSQL integration verification prove that existing valid rows
  accept the lifecycle constraint and invalid terminal state writes are rejected.

## Revisit If

- Historical analysis must reproduce the complete experience text rather than its
  stored quote and version.
- A verdict beyond matched, partial, missing, and insufficient evidence is needed.
- Retrieval design requires multiple supporting experiences per requirement.
