# ADR-025: Evidence Matcher Evaluation V1

## Status

Superseded in part by ADR-027; original v1 evidence remains immutable

## Context

ADR-024 defines the offline typed matcher boundary, but strict schemas and
adversarial unit tests do not measure whether a future real matcher chooses the
right verdict and evidence. The next stage needs reproducible development and
holdout inputs without calling a provider, reopening retrieval tuning, or using
personal resume and Job data.

## Decision

Reuse the reviewed synthetic Experience corpus from retrieval v2. Add independent
matcher development and holdout case files whose candidate lists are explicit,
ordered, and limited to five Experiences from one synthetic profile. These lists
are matcher inputs, not a new retrieval-quality result.

Matcher v1 contains 12 development and 8 holdout cases. Each split is balanced
across `matched`, `partial`, `missing`, and `insufficient_evidence`, and includes
multilingual, prompt-injection, hard-negative, composite, and explicit
retrieval-miss coverage. Positive labels carry one Experience ID/version,
`source_ref`, and exact quote. Dataset validation rejects duplicate IDs,
cross-profile candidates, stale versions, ungrounded quotes, incorrect split
sizes, verdict imbalance, and inconsistent retrieval-miss tags.

Use a review manifest containing SHA-256 hashes for the Experience corpus and both
case files. Generated labels cannot mark themselves as author-approved. The
project author approved the checked-in labels on 2026-10-04, so the manifest is
now `approved_frozen` with a reviewer and timestamp. Approval authorizes only the
offline fake run.

The development runner is fake-only in P1-5b, refuses output overwrite, and
unconditionally rejects the holdout split. Real-provider development remains a
separately authorized P1-5c action. Holdout execution remains a separate P1-5d
runner after provider, model, prompt, schema, retry policy, success criteria, and
all code hashes are frozen.

Report schema pass rate, provider and output failures, per-verdict precision,
recall and F1, macro-F1, exact verdict/evidence match, citation validity,
unsupported-positive rate, gap accuracy, confidence Brier score, tokens, and
observed matcher latency. Report matcher-only metrics on cases whose gold evidence
is available in candidates, and end-to-end metrics on every case. This prevents a
retrieval miss from being reported as a matcher selection error while keeping its
effect visible in the complete pipeline result.

## Alternatives Considered

- Reuse retrieval development and holdout queries as matcher labels: rejected
  because retrieval relevance can allow multiple Experiences and does not define
  one final matcher verdict or citation.
- Generate candidates during every matcher evaluation: rejected because retrieval
  changes would make matcher comparisons non-reproducible.
- Mark generated labels approved automatically: rejected because that would make
  the implementation its own reviewer.
- Run the fake development report before review: rejected because even
  deterministic output can anchor label edits and create misleading saved metrics.
- Use one combined score: rejected because schema, verdict, retrieval availability,
  citation safety, and provider availability fail independently.

## Consequences

P1-5c can later send only reviewed synthetic development inputs through the same
typed matcher boundary. The holdout remains inaccessible to the development runner.
The small single-reviewer dataset limits external validity, and the deliberately
frozen candidate lists do not replace P1-4 retrieval evidence.

No worker, provider factory, public API, database schema, retrieval parameter, or
production Analysis Run behavior changes in this stage.

## Verification Or Evidence

- Checked-in data validation covers case counts, verdict balance, profile isolation,
  exact quotes, multilingual and adversarial quotas, and retrieval-miss consistency.
- Metric tests prove matcher-only metrics exclude retrieval misses while end-to-end
  metrics retain them.
- Runner tests prove approved-hash enforcement, unconditional holdout refusal,
  immutable output, and offline fake development execution.
- The saved 2026-10-04 fake development report completed all 12 cases with no
  provider or output failure. Its scores are pipeline evidence, not semantic
  matcher-quality evidence.
- No real provider request or matcher holdout execution is part of P1-5b.

## Revisit If

- Author review changes labels, case counts, or verdict definitions.
- Development evidence shows confidence is unusable or multiple citations are
  necessary.
- A new holdout is needed after this holdout influences prompt or model selection.

## 2026-10-04 Update

ADR-027 replaces the single-verdict, single-canonical-citation development rubric
with oracle and candidate-conditioned verdicts plus acceptable evidence sets. The
development manifest is therefore pending author review. Historic v1 reports and
their hashes remain unchanged; matcher holdout remains sealed.
