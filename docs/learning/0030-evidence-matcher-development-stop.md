# 0030 Evidence Matcher Development Stop

## What Changed

CareerOps evaluated prompt versions v3, v4, and v5 with machine-frozen Groq
configuration and coverage-direction gates. Strict structured output now binds
positive verdicts to an evidence object, gap verdicts to null evidence, and
confidence to `[0, 1]`. Prompt v4 is retained as the current development candidate.

## Why Development Stopped

Prompt v4 passed every safety gate but missed one real partial-evidence opportunity.
Prompt v5 made the classification algorithm more explicit but missed two partial
cases. Continuing to tune against the same 12 cases would increasingly optimize
for known examples instead of testing a stable contract.

The original strict quality gate remains failed. On 2026-10-05 the author
explicitly accepted the single measured `partial -> gap` underclaim as an MVP
product limitation and froze prompt v4 for holdout readiness. This policy
override does not relabel the result as a gate pass.

## Failure Modes Prevented

- Moving acceptance gates after seeing an unfavorable result.
- Treating zero overclaims as sufficient while hiding useful partial evidence.
- Repeatedly sampling the development set until one run happens to pass.
- Reading an outdated holdout and then using it as another tuning set.
- Enabling a real worker matcher before semantic quality is accepted.

## Verification

All 36 requests completed without provider or output failure. Prompt v4 achieved
11/12 matcher-only coverage with zero overclaims, but the frozen quality gate
failed on one partial-to-gap result and `5/6` acceptable evidence. Prompt v5 did
not improve that direction.

## What You Must Understand

Level 1: safety and usefulness are separate. A conservative matcher can avoid
inventing claims yet still fail the product by hiding real evidence that could
strengthen a resume.

Level 1: safety gates protect evidence integrity; quality metrics measure how much
useful evidence the matcher surfaces. An author can accept a measured quality
limitation without weakening the safety gates or rewriting historical evidence.

Level 2: the run manifest hashes prompt text and response schema and fixes provider
settings before network access. The report stores actual failures and denominators;
it does not silently retry semantic or schema failures into a better result.

## Knowledge Check

1. Why is prompt v4 safer than prompt v3 even though both emitted grounded quotes?
2. Why did prompt v5's higher four-class exact score not make it the selected prompt?
3. Why is a partial-to-gap error a product-quality problem rather than an evidence-integrity violation?
4. Why does the policy override not mean the original quality gate passed?
