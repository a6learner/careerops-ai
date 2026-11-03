# 0056 Batched Evidence Matching

## What Changed

- **Batching.** The worker sends a run's requirements to the matcher in batches
  of at most 6, one call per batch, one after another (ADR-049).
- **Validation.** Every batch is validated on its own.
- **Whole-run failure.** If any batch fails, the whole run fails and nothing is
  stored. If all batches pass, every match is stored in one transaction.
- **Versioning.** New runs carry `matcher-batch-6` in their pipeline version.
  Older runs without it keep the single-call behavior.

## Why It Exists

In large_scale_v1 the single call had an 800-token output cap. About 54 output
tokens per requirement plus about 136 fixed fills that cap near 12
requirements. Success fell from 29/31 at 1–5 requirements to 0/44 at 16 or
more, and the median job has 11 requirements. A full batch of 6 needs about 460
tokens.

## Failure Modes It Prevents

- Large jobs failing because the answer cannot fit in the output budget.
- One oversized call making the whole run's cost and failure risk grow with the
  job.
- Old queued runs changing behavior silently after a deploy: the batch size is
  read from the run's own pipeline version.

## How It Was Verified

- Unit tests cover:
  - Batch boundaries.
  - Ordering and summed tokens.
  - Per-batch experience scoping.
  - A failing middle batch.
  - The legacy single-call path.
- A PostgreSQL integration test submits through the API and checks that 13
  requirements from batches of 6, 6 and 1 are stored in one completion.
- All gates pass (ADR-049).

## What The Real-Provider Check Showed

`docs/metrics/2026-11-02-matcher-batching-dev.md`:

- **Success.** 107/150 analyses succeeded, against 59/150 with one call. Jobs
  with 16 or more requirements: 21/44, against 0/44.
- **Over-claiming on the same pairs.** It moved within run-to-run variation:
  two single-call runs gave 4 and 7 over-claims, and two batch-6 runs gave 10
  and 8.
- **Remaining failures.** They are mostly single batches that hit the 800-token
  cap. Rescuing them with a larger cap or smaller batches works, but those
  large jobs then show about 8% over-claiming. The default stays where it is
  until the author decides.
- **Lesson.** A quality metric measured only on the runs that succeed can look
  better than the system is. Once batching let large jobs succeed, their
  over-claiming became visible.

## What The Author Must Understand

- **Atomicity is kept by deferring persistence, not by a transaction per batch.**
  Validated matches are collected in memory and written once, so the evidence
  constraints and the run-lifecycle CHECK see exactly what they saw before.
- **Why whole-run failure.** A partial result would need a new
  "not analysed" state. Reporting a failed batch as a gap would be a false
  negative claim about the user.
- **Why the version goes in the pipeline string.** Durable work items must
  execute with the semantics they were created with. Recovery can re-run an old
  queued run after a deploy.
- **The trade-offs.** More calls and input tokens per run, latency that grows
  with job size, and a model that no longer sees other requirements in the same
  call.

## Knowledge Check

1. A job has 14 requirements. How many matcher calls does a new run make, and
   what are the batch sizes?
2. Batch 2 of 3 returns a duplicate requirement ID. What is stored in
   `evidence_matches`, and which error code does the run get?
3. Why does `matcher_batch_size_from_pipeline` return `None` instead of the
   current batch size for an old pipeline version?
4. Why were batches not run in parallel, given that it would cut latency?
5. Where does the 6-requirement batch size come from, and what evidence would
   make you change it?
6. Why was the old single-call behavior re-run on the same day, instead of
   comparing batch 6 directly with the large_scale_v1 numbers?
7. A 1,600-token cap rescues 39 of 43 failed jobs. Why was it not adopted?
