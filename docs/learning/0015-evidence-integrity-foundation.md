# Evidence Integrity Foundation

## What Changed

The project now has the first evidence-matching slice:

- `analysis_runs` identifies one immutable analysis attempt against an exact parse
  run.
- `evidence_matches` stores one requirement verdict and its optional supporting
  experience quote.
- A pure validator checks ownership, candidate membership, experience version, and
  exact source grounding after whitespace normalization.
- Invalid positive claims become `insufficient_evidence` and increment the run's
  validation failure count.
- A result service and repository write the succeeded transition and every evidence
  row in one database transaction.

This slice does not retrieve candidates or call an LLM. All tests are deterministic
and cost nothing.

## Why It Exists

An LLM can produce valid JSON that is still factually wrong. Schema validation only
answers "does this output have the expected shape?" Evidence validation answers
"does this claim point to text the current user actually owns?"

The database cannot efficiently decide whether a quote is a substring of a
particular structured experience candidate. Python performs that semantic check.
PostgreSQL then enforces the structural invariant: a positive verdict cannot be
stored without an experience, version, quote, and successful validation flag.

## Failure Modes It Prevents

- A model invents an experience ID.
- A model cites another user's experience.
- A model cites an experience that retrieval did not expose as a candidate.
- The experience changed after retrieval and the model cites a stale version.
- A plausible quote does not occur in the stored experience.
- A worker updates the run to succeeded but crashes before evidence rows are saved.
- Two requests concurrently create active work for the same job input.

## How It Was Verified

- Pure unit tests exercise each validation branch.
- SQLAlchemy metadata tests check table and constraint declarations.
- The migration has a reversible downgrade.
- The PostgreSQL integration test intentionally attempts an invalid positive write
  and verifies that both the run transition and evidence insert roll back.

## What You Must Understand

Level 1:

- Schema validation, semantic validation, and database constraints solve different
  problems; none replaces the others.
- A transaction is all-or-nothing. Flushing the run update and evidence inserts in
  the same transaction prevents a succeeded run with incomplete results.
- A partial unique index protects a concurrency invariant at the database layer,
  where simultaneous requests can actually be serialized.

Level 2:

- `validate_evidence_match` is pure and therefore cheap to test.
- `flush()` sends SQL and exposes constraint failures without committing.
- `commit()` makes the run transition and all evidence rows visible together.
- `downgrade()` removes child tables before parent tables because of foreign keys.

## Knowledge Check

1. Why is a candidate ID safer than allowing the model to return any experience ID?
2. Why must `partial` have the same grounding fields as `matched`?
3. What state remains after the evidence insert fails after the run update was flushed?
4. Which checks belong in Python, and which structural invariant belongs in PostgreSQL?
5. Why is `experience_version` stored even though `experience_id` already exists?
6. What additional design is needed to reconstruct the full source of an old analysis after an experience is edited?
