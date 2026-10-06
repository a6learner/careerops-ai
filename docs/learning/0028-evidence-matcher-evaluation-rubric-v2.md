# 0028 Evidence Matcher Evaluation Rubric V2

## What Changed

Matcher development cases now distinguish the full-library answer from the
answer that is possible using only the frozen candidates. Positive labels accept
multiple grounded evidence choices, while one canonical quote remains available
for exact-agreement diagnostics. Gap labels now record why evidence is missing or
insufficient.

Prompt v2 is now the active matcher prompt contract. It defines the exact
`missing`/`insufficient_evidence` boundary, restricts `partial` to independently
separable composite conditions, and treats unverified metrics as atomic gap
claims. Existing Analysis work bound to prompt v1 remains version-bound to v1.

The existing complete Groq development output was replayed through the new
scorer. Replay used the saved raw verdicts and citations and made no provider
request.

After author approval and freeze, one paced prompt-v2 development run made 12
authorized requests. Eleven outputs passed schema validation and one was durably
recorded as `invalid_schema`; there was no provider failure or fake fallback.

## Why It Exists

Retrieval, matching, and evaluation can fail independently. A retriever may omit
the best Experience, a matcher may choose the wrong verdict from the candidates,
or an evaluator may reject a valid longer quote. One combined score cannot show
which component should change.

## Failure Modes It Prevents

- Counting a retrieval miss as a matcher mistake.
- Rewarding a matcher for claiming evidence unavailable in its candidates.
- Calling plans or study evidence `partial` implementation.
- Calling related work partial evidence for an unverified metric or causal result.
- Treating adjacent technology as an explicit mention of the required one.
- Rejecting a grounded full sentence because the label stored a shorter phrase.
- Reusing an old approval after labels or hashes change.
- Tuning against matcher holdout.

## How It Was Verified

The replay completed all 12 saved cases with zero provider and output failures.
Matcher-only verdict accuracy is `7/12` (`0.5833`), while end-to-end verdict
accuracy is `6/12` (`0.5000`). The difference is the intentional retrieval miss:
the model correctly returned `partial` for the available candidates while the
full library supports `matched`.

All six positive outputs cited the correct candidate Experience ID/version and
source and contained an acceptable grounded quote. Therefore matcher-only
Experience ID, source, and acceptable-evidence accuracy are each `1.0000`.
Canonical exact agreement is `0.0000` because each model quote was a grounded
full sentence rather than the shorter canonical fragment. Citation validity is
`1.0000`, and unsupported-positive rate is `0.0000`.

Two verdict errors remain after separating three `missing` versus
`insufficient_evidence` mistakes attributable to the legacy prompt's broad
"relevant" wording. All five remain wrong under v2; attribution does not grant
alternate-label credit. The development manifest is pending author review, and
the matcher holdout case file was not loaded or run.

The report now includes both `end_to_end_per_verdict` and
`matcher_only_per_verdict`. The v1 replay has matcher-only recall `1.0000` for
`matched`, `0.7500` for `partial`, `0.0000` for `missing`, and `0.6667` for
`insufficient_evidence`. The legacy ambiguity attribution is stored outside the
generic summary and is enabled only because the source report records prompt v1.

The new prompt-v2 run improved the `missing` class to `1.0000` recall, but it did
not pass the frozen gates: matcher-only verdict accuracy was `8/12`, macro-F1 was
`0.6810`, one output failed schema validation, and acceptable-evidence accuracy
was `5/6`. Citation validity remained `1.0000` and unsupported-positive rate
remained `0.0000`. Holdout therefore stays sealed.

## What You Must Understand

Level 1: end-to-end metrics answer whether the system found and judged the right
evidence. Matcher-only metrics answer whether the model made the right decision
given exactly what retrieval supplied.

Level 1: quote grounding is a safety invariant. Canonical wording agreement is a
diagnostic about selection style and must not replace grounding validation.

Level 2: dataset hashes bind approval to exact bytes. Changing labels invalidates
the old approval even when code and provider stay unchanged.

Level 2: prompt version is part of the durable Analysis pipeline fingerprint.
New work uses v2, while already queued v1 work must not be silently reinterpreted.

## Knowledge Check

1. Why is `matcher-dev-009` wrong end to end but correct matcher-only?
2. When should a future plan be `insufficient_evidence` rather than `partial`?
3. Why can acceptable-evidence accuracy be `1.0` while canonical exact agreement
   is `0.0`?
4. Which two metrics remain hard positive-claim safety gates?
5. Why must the next development run use a new report instead of resuming the v1
   report?
6. Why does one `invalid_schema` result block holdout even when every accepted
   positive citation is grounded?
