# Evidence Matcher V1 Review Guide

## Status

Evaluation rubric v2, development labels, prompt v2, and acceptance gates were
approved and frozen by the project author on 2026-10-04 America/Los_Angeles. The
first prompt-v2 development run did not pass those gates. Prompt v4 was later
accepted for holdout readiness through an explicit policy override that preserves
the original quality-gate failure. The holdout was opened once for rubric-v2
migration and now awaits review under `HOLDOUT_V2_REVIEW_PACKET.md`.

## Files

- Corpus: `evals/evidence_retrieval_v2/experiences.json`
- Development: `evals/evidence_matcher_v1/development_cases.json`
- Manifest: `evals/evidence_matcher_v1/review_manifest.json`

## Review Each Case

1. The requirement is synthetic and contains no real resume or JD data.
2. Every candidate belongs to the named synthetic profile.
3. `matched` means one Experience supports every necessary condition.
4. `partial` means one Experience supports only part of a composite requirement.
   Those parts must be independently separable conditions.
5. `missing` means candidates contain no explicit mention of the required
   technology, capability, or result.
6. `insufficient_evidence` means the same technology, capability, or result is
   explicit but only planned, learned, discussed, negated, or unverified.
7. Each gap reason code explains the concrete boundary used for that label.
8. `oracle_verdict` is correct against the full synthetic profile;
   `candidate_conditioned_verdict` is correct against the listed candidates.
9. Every `acceptable_evidence` Experience ID/version/source is correct, and each
   quote is an exact substring of that source.
10. A longer grounded quote containing an acceptable fragment is valid;
    canonical exact agreement remains diagnostic.
11. Retrieval-miss cases may legitimately have different oracle and
    candidate-conditioned verdicts.
12. Prompt-like text is treated as data, not as an instruction.
13. Related work without a requested verified metric, measured result, or causal
    outcome is `insufficient_evidence`, not `partial`.

## Freeze Procedure

For the migrated holdout, update only `holdout_v2_run_manifest.json` reviewer,
reviewed timestamp, status, and notes. Do not edit a case after approval without
returning the manifest to pending and recomputing every affected hash. Approval
does not authorize a provider request; the one-time run also requires the separate
invocation-local holdout opt-in.
