# 0025 Offline Real Evidence Matcher Contract

## What Changed

The Evidence Matcher now consumes a versioned typed input rather than repository
objects. It receives requirements, a deduplicated set of candidate Experiences,
named source fields, and each requirement's ranked candidate IDs.

A strict offline response schema distinguishes positive verdicts from gaps. The
execution service also records specific provider and output failure categories.
The fake matcher uses the same contract, so CI still runs without a network or
provider cost.

## Why It Exists

A real model is an untrusted producer. Its JSON shape, selected IDs, quote, and
confidence must not become database truth merely because the HTTP request
succeeded. Defining and attacking the boundary offline separates application
correctness from later provider quality.

## Failure Modes It Prevents

- Sending user IDs, vectors, scores, or non-candidate Experiences to a provider.
- Prompt-like text inside a requirement or Experience changing the system rules.
- Omitted, duplicated, or invented requirement IDs becoming silent gaps.
- Gap verdicts carrying hidden positive evidence.
- Positive verdicts citing another user, a non-candidate, a stale version, or an
  unsupported source quote.
- Invalid JSON and provider outages being reported as successful analysis.
- A fake fallback hiding real-provider failure.

## How It Was Verified

Focused offline tests cover input construction, strict response parsing, fake
matching, exact quote grounding, adversarial citations, coverage validation, and
error-code mapping. This stage makes no real provider request and produces no
matcher quality metric.

## What You Must Understand

Level 1: schema validity proves only that output has the expected shape. Ownership,
candidate membership, version, and exact quote validation prove whether a positive
claim is supportable.

Level 1: malformed coverage fails the whole run because it is a producer failure.
A structurally valid but unsupported positive claim is downgraded so one bad claim
does not discard every valid requirement result.

Level 1: the model supplies a source reference and exact quote; the server derives
the span. Model-generated offsets are not trusted.

Level 2: the fake matcher implements the same typed protocol as a future real
adapter, while provider-specific HTTP, prompt rendering, and schema parsing remain
outside the service layer.

## Knowledge Check

1. Why is an omitted requirement a failed output rather than a `missing` verdict?
2. Why does an unknown Experience ID downgrade one claim instead of failing the
   complete Analysis Run?
3. Why is `source_ref + exact quote` safer than accepting a normalized quote from
   any Experience field?
4. What does confidence mean, and which validations can it never override?
5. Why must provider failure not switch to the fake matcher under the same run?
6. Which evidence guarantees are enforced in Python, and which are enforced by the
   database?
