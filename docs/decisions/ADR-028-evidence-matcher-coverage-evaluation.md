# ADR-028: Evidence Matcher Coverage Evaluation

## Status

Accepted; prompt v4 accepted for holdout readiness with a measured limitation

## Context

The persisted matcher contract distinguishes `matched`, `partial`, `missing`, and
`insufficient_evidence`. That four-way result is useful diagnosis, but it gives a
gap-subtype disagreement the same weight as an overclaim. CareerOps primarily
needs to tell users what their current material fully proves, partly proves, or
does not yet prove without turning a resume omission into a claim about ability.

The first prompt-v2 development run illustrates the difference. A future Rust
plan labeled `missing` instead of `insufficient_evidence` is still a gap. In
contrast, labeling partial offline synchronization evidence `matched` overstates
support for encrypted server storage.

## Decision

Keep the existing four persisted verdicts and derive evaluation-only coverage:

- `matched` maps to `full`;
- `partial` maps to `partial`;
- `missing` and `insufficient_evidence` map to `gap`.

No provider, database, or public API field is added. Four-class exact verdict
accuracy and gap-subtype differences remain diagnostic. Primary coverage metrics
use every development case as the denominator. Provider and output failures count
as incorrect and are never converted into a gap. A schema-valid-only metric is
reported separately and labeled diagnostic.

Record error direction explicitly:

- overclaim: `gap -> partial`, `gap -> full`, or `partial -> full`;
- underclaim: `partial -> gap`, `full -> partial`, or `full -> gap`;
- gap-subtype difference: four-class mismatch whose expected and predicted
  coverage are both `gap`;
- provider/output failure: no semantic verdict inferred.

Citation validity continues to answer whether the quote is real and grounded.
Coverage overclaim answers whether that real quote proves the required scope.
Neither metric substitutes for the other.

## Prompt-V2 Offline Rescore

The immutable coverage-v1 report rescored the existing prompt-v2 report with zero
provider calls:

- matcher-only coverage: 9 / 12 (`0.7500`);
- matcher-only coverage among schema-valid outputs: 9 / 11 (`0.8182`), diagnostic;
- four-class exact verdict: 8 / 12 (`0.6667`);
- one gap-subtype difference (`matcher-dev-004`);
- one output failure (`matcher-dev-008`);
- one `partial -> gap` underclaim (`matcher-dev-009`);
- one `partial -> full` overclaim (`matcher-dev-010`);
- `gap -> positive`: 0 / 6;
- citation validity: 5 / 5;
- unsupported positive: 0 / 5.

## Frozen Prompt-V3 Development Gates

Safety hard gates:

- schema pass `1.0`, provider failures `0`, output failures `0`;
- citation validity `1.0`, unsupported-positive count `0`;
- all coverage overclaim counts `0`, including `gap -> positive` and
  `partial -> full`.

Primary quality gates:

- all-case matcher-only coverage at least 10 / 12;
- `partial -> gap` count `0`, because it hides proven resume-strengthening
  evidence;
- every coverage class has non-zero recall.

Matcher-only acceptable-evidence accuracy must also be `1.0`. Four-class exact
verdict accuracy, gap-subtype accuracy, confidence, canonical
quote agreement, and schema-valid-only coverage remain diagnostics. These gates
are machine-evaluated under `evidence-matcher-development-gates-v3`. They are not
retroactively applied to claim that the first prompt-v2 run passed.

## Prompt Iterations And Selection

Prompts v3 through v5 kept the same typed input and output fields. They tested a
general decision procedure: split requirements into necessary conditions,
evaluate each Experience independently, require one Experience to prove every
condition for `matched`, and retain the conservative atomic-metric rule.

The Groq response schema now expresses positive and gap variants as a supported
JSON Schema `anyOf`, so positive verdicts require an evidence object and gap
verdicts require `null`. Confidence is constrained to `[0, 1]`. This changes no
provider output slot, database field, or public API.

Every real run used an immutable machine-bound manifest. Prompt v4 is the selected
development candidate under
`evals/evidence_matcher_v1/prompt_v4_selected_development_manifest.json`:

- prompt SHA-256 `ef33e71c303438a876c53ef026c47c38fe9c9331ecb3cc5b00d3b3d680b24b5a`;
- response-schema SHA-256 `bf2c87f276da75998a6d2421f661316a50e9b608304642a4223e6824c4307902`;
- same frozen corpus and development labels;
- `openai/gpt-oss-20b`, one attempt per case, 12-request budget, 11-second
  request spacing, 800 completion-token ceiling, low reasoning, temperature 0.

The project author's instruction to finish P1-5 and independently perform needed
Groq calls authorized three bounded development comparisons. Prompt v4 was
selected because it had the highest matcher-only coverage, zero overclaims, and
fewer partial-to-gap misses than v5. The original frozen result remains a safety
pass and quality fail because one partial case was reported as a gap and matcher-
only acceptable-evidence accuracy was `5/6`.

On 2026-10-05, after seeing those measurements, the project author explicitly
accepted the conservative `partial -> gap` limitation for the MVP and selected
prompt v4 as the development candidate for holdout readiness. This is policy
override `author-accepted-prompt-v4-underclaim-2026-10-05`, not a retroactive
change to the frozen quality gate and not a claim that the old gate passed. No
further prompt, label, evaluator, or retrieval tuning is allowed against the
development set.

Safety gates and product-quality gates are now named separately. Schema/output
reliability, grounded citations, unsupported positives, `gap -> positive`, and
`partial -> matched` protect evidence integrity. Coverage, four-class exactness,
and `partial -> gap` measure usefulness. The latter must remain visible with its
full denominator even when the author accepts it as an MVP limitation.

## Safe Invalid-Output Diagnostics

Future invalid JSON/schema results record only:

- failure category;
- Pydantic error location and error type, excluding rejected input values;
- response SHA-256 and UTF-8 byte size;
- provider-reported input/output tokens when available.

Do not persist the raw provider response, prompt, Experience text, or validation
input. The existing `matcher-dev-008` report predates this instrumentation, so
its exact invalid field and failed-response token usage remain unknown. Historical
evidence is not rewritten.

## User-Facing Language

- Full: “Your current materials demonstrate all listed conditions.”
- Partial: “Your current materials demonstrate these conditions; these other
  conditions are not yet evidenced. If you genuinely performed them, add the
  concrete details.”
- Gap: “Your current materials do not yet demonstrate this requirement.”

Never turn “not currently evidenced” into “you cannot do this,” and never suggest
inventing an Experience, metric, technology, or result.

## Alternatives Considered

- Replace four verdicts with three: rejected because gap subtype remains useful
  diagnosis and would change persisted/public contracts.
- Add covered/uncovered conditions to provider output now: rejected because the
  existing contract can first be evaluated with derived coverage.
- Exclude failures from primary accuracy: rejected because availability and
  schema reliability are part of end-to-end usefulness.
- Treat grounded citations as sufficient safety: rejected because a true quote
  can still fail to cover the whole requirement.

## Consequences

Evaluation becomes more aligned with user value and overclaim risk without a
migration or contract expansion. Prompt v4 is frozen for the one-time matcher
holdout, but remains excluded from the production worker. Historical prompt-v2
through prompt-v5 reports and their original gate results remain immutable.

## Verification Or Evidence

- Targeted tests cover the 9/12 denominator, failure treatment, dev-004, dev-008,
  dev-009, dev-010, immutable output, holdout refusal, and all requested error
  directions.
- `docs/metrics/2026-10-04-groq-evidence-matcher-development-prompt-v2-coverage-v1.json`
  is the machine-readable zero-request result.
