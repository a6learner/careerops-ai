# 0058 Evidence Matcher Output Cap (2,000 Tokens)

## What Changed

- New analysis runs let each matcher call produce up to 2,000 output tokens
  instead of 800 (ADR-051).
- The cap is stored on the run as a `matcher-cap-2000` segment of its pipeline
  version, and the worker reads it from there.
- Older runs, which have no segment, keep 800.

## Why It Exists

After batching and the heading filter, the main remaining failure was truncation.
`gpt-oss-20b` spends reasoning tokens from the same budget, so a batch of six that
usually needs about 440 tokens sometimes runs past 800 and is cut off mid-answer.

The 800 limit was chosen for Groq's free-tier tokens-per-minute budget, not for
correctness. In development data, a 1,600 cap rescued 39 of 43 failed jobs.

## Failure Modes It Prevents

- Large jobs failing with `finish_reason=length` even though the model's answer
  is valid.
- Recovered or queued runs silently changing their cap after a deploy: the cap
  travels with the run.

## How It Was Verified

- Unit tests for the pipeline segment (position, legacy, invalid) and for the
  resolver applying 2,000 or 800.
- All gates pass (ADR-051).
- Real-provider check: `docs/metrics/2026-11-03-matcher-cap-dev.md`.

## What The Author Must Understand

- **Why a flat raise and not a retry.** A token cap only stops generation. Any
  answer shorter than 800 tokens is not affected by a 2,000 cap, so raising the
  cap only changes calls that would have been cut off. Two separate runs still
  differ by sampling.
- **Why the cap is versioned.** It changes what a run can produce, so it belongs
  to the run's identity, like the batch size (ADR-049).
- **What this does not fix.** Hard large jobs over-claim at about 8% whether they
  are rescued by a bigger cap or by smaller batches. The cap makes that visible;
  the next stage must reduce it.

## Knowledge Check

1. A batch's answer needs 650 tokens. What differs between an 800 cap and a
   2,000 cap?
2. Why does `gpt-oss-20b` hit the cap more often than its visible JSON length
   suggests?
3. A run was queued before this change and recovered after the deploy. Which cap
   does it use, and where does the worker read that from?
4. Why does a bigger cap matter more on Groq's free tier than on a paid route?
5. Why was the over-claim analysis split by output length before choosing a flat
   raise?
