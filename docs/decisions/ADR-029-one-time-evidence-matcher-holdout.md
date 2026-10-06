# ADR-029: One-Time Evidence Matcher Holdout

## Status

Accepted; one-time holdout completed on 2026-10-05

## Context

Prompt v4 passed the frozen development safety gates with 11/12 coverage, zero
overclaims, zero unsupported positives, and 5/5 grounded citations. It failed the
original quality gate on one `partial -> gap` underclaim and 5/6 acceptable-
evidence accuracy. The author accepted that measured conservative limitation for
the MVP without rewriting the historical gate result.

The legacy matcher holdout used a single expected verdict/evidence shape. It
could not correctly separate full-library truth from what the frozen Top-5 lets
the matcher see, and the existing development runner intentionally rejects it.

## Decision

Freeze the one-time holdout identity to:

- prompt `evidence-matcher-prompt-v4` and schema
  `evidence-matcher-schema-v1`;
- Groq `openai/gpt-oss-20b`, low reasoning, temperature 0, maximum 800 output
  tokens, and at least 11 seconds between request starts;
- eight request slots and exactly one provider attempt per case;
- the coverage-v2 evaluator and `evidence-matcher-holdout-safety-v1` policy;
- the author-accepted development limitation identified by
  `author-accepted-prompt-v4-underclaim-2026-10-05`.

Use a separate invocation-local `CAREEROPS_RUN_MATCHER_HOLDOUT=1` authorization.
Development authorization does not enable holdout. The development runner keeps
rejecting holdout data.

Before each request, atomically checkpoint the case as in progress and consume a
request slot. After completion, atomically checkpoint the real result. A restart
skips completed cases. An in-progress case has an ambiguous provider outcome, so
it becomes an explicit `provider_outcome_unknown_after_local_interruption`
failure and is never called again. This provides at-most-once provider attempts;
it deliberately prefers a visible failed holdout to a hidden duplicate sample.

Provider and output failures stay failures. They are never converted into a
semantic gap. The final report is written once and cannot be overwritten.

Safety hard gates over all eight cases are:

- schema pass 8/8;
- provider failures 0 and output failures 0;
- citation grounding 100% of emitted positives;
- unsupported positive 0;
- `gap -> positive` 0;
- `partial -> matched` 0.

Coverage, four-class exactness, and `partial -> gap` remain quality diagnostics
with failures included in the denominator. Any failed safety gate blocks real-
matcher worker integration. A quality limitation may be reviewed separately but
must not be hidden.

The first holdout opening is limited to migrating labels to rubric v2 and
preparing author review. It may not influence prompt, retrieval, schema, or
evaluator behavior. The migrated file records oracle and candidate-conditioned
verdicts, acceptable evidence, canonical evidence, and necessary gap reasons.

## Alternatives Considered

- Reuse the development runner: rejected because authorization, recovery, and
  immutable one-time evidence need an independent boundary.
- Retry an ambiguous in-progress case: rejected because it could silently sample
  the holdout twice.
- Convert provider/output failures to gaps: rejected because availability is part
  of holdout validity.
- Treat all conservative misses as safety failures: rejected because
  `partial -> gap` loses product value but does not invent evidence.
- Add provider, database, or API fields: rejected; the existing four verdicts and
  evaluation-only coverage are sufficient for this stage.

## Consequences

The runner can resume without recalling completed or ambiguous cases, and every
outcome remains in the denominator. A local interruption may permanently fail the
one-time run; this is an intentional integrity trade-off. No database migration,
public API change, retrieval change, or worker integration is introduced.

The author approved and froze the migrated manifest before execution. The
one-time run consumed all eight request slots and produced an immutable final
report. It must not be repeated or used as a tuning set.

## Verification Or Evidence

Toy fixtures cover the full eight-slot lifecycle, completed-prefix recovery,
ambiguous-attempt fencing, provider/output failure preservation, manifest and
model fencing, independent authorization, fixed prompt use, budget accounting,
and immutable output. The toy tests do not reference the real holdout path.

The authorized run passed every frozen safety gate: schema 8/8, zero provider
or output failures, citation grounding 1/1, unsupported positives 0/1,
`gap -> positive` 0/5, and `partial -> matched` 0/2. Matcher-only coverage was
6/8 and both partial cases became gaps. These quality limitations remain visible
and did not change the pre-frozen policy.

Evidence:

- `docs/metrics/2026-10-05-groq-evidence-matcher-holdout.json`
- `docs/metrics/2026-10-05-groq-evidence-matcher-holdout.md`
