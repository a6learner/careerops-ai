# 0026 Evidence Matcher Evaluation V1

## What Changed

CareerOps now has synthetic Evidence Matcher development and holdout case files,
hash-bound review metadata, a fake-only offline evaluator, separated matcher-only
and end-to-end metrics, and a development runner that refuses the holdout.

The project author approved and froze the labels on 2026-10-04. A checked-in fake
development report now proves the evaluation pipeline runs offline; its scores do
not measure real matcher semantic quality.

## Why It Exists

Application tests can prove that unsupported claims are blocked, but they cannot
prove that a model usually chooses the correct verdict or evidence. A versioned,
reviewed dataset makes future model output comparable without sending real resume
or Job data.

## Failure Modes It Prevents

- Editing labels without changing a recorded hash.
- Treating a retrieval miss as a matcher selection error.
- Hiding retrieval misses by reporting matcher-only scores alone.
- Reporting one combined score that obscures citation or schema failures.
- Running the holdout during development.
- Overwriting historical evaluation evidence.
- Treating fake matcher output as real semantic-quality evidence.
- Generated labels falsely claiming project-author approval.

## How It Was Verified

Offline tests load both checked-in splits, validate every exact quote and candidate
boundary, exercise metric formulas, enforce the approved hashes, reject holdout
execution, and prove report immutability. The approved fake development run
completed all 12 cases with zero provider or output failures and preserved the raw
and validated results. No real-provider or holdout request was made.

## What You Must Understand

Level 1: matcher-only metrics answer whether the matcher chose correctly when the
needed evidence was available. End-to-end metrics also include retrieval misses.
Both are required, and neither replaces the frozen P1-4 retrieval evaluation.

Level 1: development labels can guide model and prompt selection; holdout labels
must not. After holdout is observed, changing the system requires a new version and
new holdout.

Level 1: citation validity and unsupported-positive rate are safety metrics.
Verdict macro-F1 is a quality metric. Provider failure and schema pass rates are
reliability metrics. They should not be collapsed into one number.

Level 2: the manifest binds raw file bytes with SHA-256. Formatting-only edits also
change the hash and invalidate approval, which is intentional.

## Knowledge Check

1. Why are retrieval-miss cases excluded from matcher-only metrics but included in
   end-to-end metrics?
2. Why does the development runner require author-approved hashes even for the fake
   matcher?
3. What is the difference between citation validity and positive evidence exact
   accuracy?
4. Why is macro-F1 more informative than accuracy for multiple verdict classes?
5. Which decisions must be frozen before the single matcher holdout run?
