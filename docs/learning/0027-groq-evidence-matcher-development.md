# 0027 Groq Evidence Matcher Development Integration

## What Changed

CareerOps now has a Groq Evidence Matcher adapter and a separate, explicitly
authorized development runner. The adapter reuses shared Groq HTTP behavior while
keeping matcher instructions, structured output, parsing, and evidence validation
separate from requirement parsing.

The first bounded run attempted all 12 synthetic development cases. Six completed
and six were rate-limited. The partial report is intentionally preserved rather
than hidden or overwritten.

The authorized paced recovery called only those six failures. All completed, the
first six results were preserved, and the merged 12-case report has no provider or
output failure. The resulting semantic metrics still do not justify holdout.

## Why It Exists

Offline schemas prove contract safety but not whether a real provider accepts the
schema or produces useful judgments. A guarded development runner tests that path
without changing production Analysis Runs or exposing real resume and Job data.

## Failure Modes It Prevents

- `.env` provider selection accidentally authorizing a live evaluation.
- A real provider call from API code or default CI.
- Parser and matcher prompts becoming one coupled contract.
- 401, timeout, 429, 5xx, invalid JSON, and invalid schema collapsing into one
  misleading failure.
- Schema-valid output bypassing candidate, ownership, version, or quote checks.
- A fake fallback hiding a real-provider outage.
- Provider retries exceeding the announced call budget.
- Holdout data reaching the provider during development.
- A failed report being overwritten by a later successful run.

## How It Was Verified

Offline tests exercise HTTP payloads and failure classification with mock
transports. The guarded real run made 12 development attempts and zero holdout
attempts. It recorded 6 completed cases, 6 `provider_rate_limited` failures, 6,567
input tokens, and 1,081 output tokens. All four emitted positive citations were
grounded; no unsupported positive claim passed validation. Partial accuracy and F1
are not complete development quality evidence.

The requests were sent in about nine seconds. The six successes already accounted
for 7,648 reported tokens, so adding request seven to the rolling minute exceeded
the model's 8K TPM limit. The Groq console showed only about 8.2K tokens for the
day, confirming that the failure was a short-window throughput limit rather than
the 200K TPD or a monthly budget. Pacing is therefore the correct recovery control;
changing verdict labels or silently switching providers would address the wrong
failure.

The recovery added 6,520 input and 742 output tokens. Across all successful cases,
the merged report contains 13,087 input and 1,823 output tokens. It achieved 0.5000
end-to-end verdict accuracy, 0.5455 matcher-only verdict accuracy, 1.0000 citation
validity, and 0 unsupported positive claims. Positive evidence exact accuracy was
0 because valid model citations did not equal the single frozen canonical quote.

These are the original v1 scores. The offline rubric-v2 rescore in learning note
0028 supersedes their interpretation without changing the raw provider report.

## What You Must Understand

Level 1: strict structured output guarantees shape, not semantic correctness. The
model can choose the wrong verdict or a different valid quote while satisfying the
schema.

Level 1: provider failure is not a gap verdict. A rate-limited case remains an
upstream failure and must never become `missing` or fall back to fake output.

Level 1: a recovery run must preserve the first artifact, use a new bounded budget,
and retry only failed cases. Otherwise successful cases would be charged twice and
the operational history would be lost. The recovery path is already implemented
and offline-tested; it still requires separate authorization before network use.

Level 2: the shared Groq transport owns HTTP mechanics only. Domain-specific
schemas, prompts, normalization, and validation stay in their adapters and service
boundaries.

## Knowledge Check

1. Why does strict JSON Schema not make an evidence claim trustworthy?
2. Why is a 429 recorded as provider failure instead of `missing` evidence?
3. Why must recovery retry only the six failed cases?
4. Which checks still run after the model returns a valid positive verdict?
5. Why does connecting this adapter to the worker remain a later stage?
6. What evidence distinguishes a TPM spike from daily-quota exhaustion here?
