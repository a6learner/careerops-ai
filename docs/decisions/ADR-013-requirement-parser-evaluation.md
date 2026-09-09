# ADR-013: Requirement Parser Evaluation

## Status

Accepted

## Context

Two successful smoke requests proved provider compatibility but could not
support a parser-quality claim. A changing language model also cannot be tested
like deterministic application code. The project needs a repeatable evaluation
that keeps labels, raw predictions, failures, token usage, and limitations.

## Decision

Maintain a versioned JSON dataset under `evals/` with synthetic JD text and
human-authored expected requirements. Validate case IDs, label grounding, and
skill normalization before making provider requests.

Score exact source-text extraction separately from category and skill accuracy.
Report extraction precision, recall, and F1; exact full-requirement metrics;
category and skill accuracy on text matches; exact-case rate; provider failures;
grounding/output failures; provider-reported tokens; and mean observed latency.

The evaluator writes a new immutable JSON evidence file and refuses to overwrite
an existing result. Live evaluation is a manual command using the configured
worker-side adapter. It is not part of CI.

The initial 12-case dataset is a development set. `parse-v2` was designed after
reviewing `parse-v1` failures on this same set, so the v2 score is not an
independent generalization result. Freeze v2 before creating a new holdout set.

## Alternatives Considered

- Count only successful API responses: rejected because transport success says
  nothing about extraction or grounding quality.
- Use an LLM judge: deferred because it adds cost and another nondeterministic
  dependency before simple exact labels are exhausted.
- Report one combined score: rejected because extraction, classification,
  skills, grounding, and provider availability fail for different reasons.
- Keep rerunning and tuning until all 12 pass: rejected because that would
  overfit the development set.

## Consequences

Metrics are reproducible against a fixed dataset and raw per-case predictions
remain reviewable. Exact matching is deliberately strict and may penalize a
semantically equivalent span, so results require qualitative error analysis.

Small synthetic results must not be presented as production accuracy. A future
holdout set should include additional English and multilingual cases without
being used to edit the prompt first.

## Verification Or Evidence

- Unit tests cover dataset validation, metric separation, false positives,
  false negatives, and provider versus grounding failures.
- `parse-v1` and `parse-v2` raw reports are saved under `docs/metrics/`.
- The comparison and known remaining error are documented in
  `docs/metrics/2026-09-08-groq-requirement-eval-summary.md`.

## Revisit If

Revisit when adding a holdout set, fuzzy span scoring, multiple annotators,
real anonymized JDs, a second provider, or statistical confidence intervals.
