# 0055 Evidence Matcher Failure Diagnostics

## What Changed

- A Groq `json_validate_failed` rejection, and an OpenRouter 200 response with
  `finish_reason` `error` or `length`, now fail the run as
  `MATCHER_OUTPUT_INVALID_SCHEMA` instead of `MATCHER_PROVIDER_FAILED`.
- A run that fails the contract check (missing, extra or duplicate requirement
  IDs, or bad evidence fields) now stores its token counts.
- The same failure logs exactly what was wrong:
  `expected=12;returned=9;missing=3;unknown=0;duplicates=0;invalid_shape=0`.
- The frontend message for `MATCHER_OUTPUT_INVALID_CONTRACT` describes the real
  cause (ADR-048).

## Why It Exists

large_scale_v1 completed only 59 of 150 analyses, and none at 16 or more
requirements. The leading explanation is the 800-token output cap: about 54
output tokens per requirement plus about 136 fixed. But the failed runs kept no
tokens and no reason, so the explanation could not be checked. You can't fix
what you can't see.

## Failure Modes It Prevents

- Telling users "the provider returned an error, try again" when the provider
  worked and the model's own output was rejected. Retrying that usually fails
  the same way.
- Misreading evaluation results: 28 failures were counted as provider failures
  when they were most likely output failures.
- Guessing at causes from aggregate correlations instead of reading the failed
  run itself.

## How It Was Verified

Fake HTTP transports only, no network:

- Adapter tests cover each provider response shape.
- Execution tests cover each coverage defect and assert the stored tokens and
  the exact diagnostic string.
- All backend and frontend gates pass (ADR-048).

## What The Author Must Understand

- **Two layers can reject output.** The provider's server-side JSON-schema
  check, and the product's own three-layer validation. Both are output
  failures, so the error code should say so wherever the rejection happens.
- **HTTP 200 is not success.** Through a router, an aborted generation can
  arrive as a 200 with `finish_reason: "error"`. The adapter must read
  `finish_reason`, not just the status code.
- **Diagnostics without user content.** The log records counts, never quotes or
  resume text.
- **A known risk.** An unrelated upstream fault reported as
  `finish_reason: "error"` is now labeled an output failure.

## Knowledge Check

1. Why was `MATCHER_PROVIDER_FAILED` the wrong code for a Groq
   `json_validate_failed` response, and which code replaces it?
2. A run logs `expected=18;returned=11;missing=7;unknown=0;duplicates=0`. What
   does that suggest about the output budget, and which stored field would you
   check next?
3. Why does `finish_reason: "length"` count as an output failure even when the
   content happens to parse?
4. Why did this stage not add a database column for failure detail?
5. What evaluation numbers from before this change can no longer be compared
   directly with numbers after it?
