# 0029 Evidence Matcher Coverage Evaluation

## What Changed

CareerOps now derives `full`, `partial`, and `gap` coverage from the existing four
matcher verdicts for evaluation only. It reports exact numerators and denominators,
schema/output failures, gap-subtype differences, overclaim directions, and
underclaim directions without changing persistence or API contracts.

Future invalid-output evidence also retains safe structural diagnostics and token
metadata without storing raw model text.

## Why It Exists

The product should distinguish “current material does not prove this” from “the
user lacks this ability.” It should also recognize real partial evidence that can
strengthen a resume while preventing a grounded but incomplete quote from being
treated as full proof.

## Failure Modes It Prevents

- Treating `missing` versus `insufficient_evidence` as equally severe as an
  unsupported positive claim.
- Hiding a schema failure by converting it into a normal gap.
- Claiming full coverage because a cited sentence is real.
- Missing partial evidence that could prompt an honest resume improvement.
- Inflating accuracy by excluding provider/output failures from the denominator.
- Persisting raw provider responses that may repeat user-controlled text.

## How It Was Verified

The saved prompt-v2 development report was rescored offline with zero provider
requests. Coverage was correct for 9 of all 12 cases and 9 of 11 schema-valid
cases. Four-class exact accuracy remained 8/12. The result contained one gap
subtype difference, one output failure, one `partial -> gap` underclaim, and one
`partial -> full` overclaim.

All five positive citations were grounded. That did not excuse the dev-010
overclaim because its quote proves synchronization, not encrypted server storage.

## What You Must Understand

Level 1: grounding proves that a quote exists in a user-owned candidate. Coverage
proves whether that quote supports all, some, or none of the JD condition.

Level 1: failures remain failures. Counting them as gaps would falsely make an
unavailable or malformed model look semantically cautious.

Level 2: safe diagnostics keep error paths operable without copying raw model
responses into durable reports. Hashes permit correlation; structural locations
permit debugging; token metadata improves cost evidence.

## Knowledge Check

1. Why is dev-004 coverage-correct but four-class-exact incorrect?
2. Why is dev-010 an overclaim even though its citation is grounded?
3. Why does primary coverage use 12 rather than 11 as its denominator?
4. Which diagnostic fields are safe to retain for a future invalid schema?
5. What language should the product use when current materials do not prove a JD
   requirement?
