# 0031 One-Time Evidence Matcher Holdout

## What Changed

CareerOps now has an independent matcher holdout runner with a frozen manifest,
separate invocation authorization, eight request slots, one attempt per case,
atomic per-case checkpoints, and an immutable final report. The legacy holdout
labels were migrated once to the dual-verdict rubric, approved by the author,
and evaluated exactly once.

## Why It Exists

A holdout only provides honest evidence if the prompt, schema, model, evaluator,
policy, and labels are fixed before model output is seen. Recovery must also avoid
quietly sampling difficult cases more than once.

## Failure Modes It Prevents

- A development opt-in accidentally authorizing holdout access.
- Recalling completed cases after a local restart.
- Retrying an ambiguous in-flight request and selecting the better sample.
- Treating a timeout, 429, 5xx, invalid JSON, or invalid schema as a normal gap.
- Changing prompt, evaluator, or model after seeing holdout labels or results.
- Overwriting the only final holdout report.
- Enabling the production worker after a failed safety gate.

## How It Was Verified

Eight-case toy fixtures exercised a complete run, prefix recovery, ambiguous
in-progress recovery, fixed budget, one attempt per case, provider and schema
failures, pending-manifest rejection, wrong-model rejection, explicit prompt-v4
selection, and final-report immutability. No provider request was made.

The migrated holdout validates against the existing corpus and remains balanced
across the four oracle verdicts. Its new hash is bound into an
`approved_frozen` manifest. The real run passed all safety gates, while
matcher-only coverage was 6/8 and partial recall was 0/2. That distinction is
why safety acceptance does not imply that matcher quality is complete.

## What You Must Understand

Level 1: at-most-once attempts make an interruption visible instead of creating a
biased second sample. PostgreSQL is not involved because this is an offline
evaluation artifact, but the same fencing principle protects durable truth.

Level 1: a grounded quote can still overclaim scope. Citation grounding and
`partial -> matched` are therefore separate safety checks.

Level 2: the checkpoint consumes a request slot before network access. Completed
results are ordered and hash-bound to the manifest and case list. Resume never
uses a development authorization flag.

## Knowledge Check

1. Why is an ambiguous in-progress request not retried?
2. Why do provider/output failures remain in the eight-case denominator?
3. Which fields make the manifest a reproducible run identity?
4. Why can `partial -> gap` be accepted while `partial -> matched` cannot?
5. Why must this completed holdout never be rerun after seeing its results?
