# Groq Evidence Matcher Prompt V2 Development Run

## Scope

The project author approved and froze matcher rubric v2, development labels,
prompt v2, and the development acceptance gates before this run. The invocation
used only the 12 synthetic development cases, `openai/gpt-oss-20b`, one attempt
per case, at most 12 requests, and at least 11 seconds between request starts.
It made zero matcher holdout requests and did not change retrieval parameters.

Machine-readable report SHA-256:
`129024cd278d1d5ac0fcef5e133db0717f34ea67df98ff7c1b601c00c7c1d24e`.

## Operational Result

- Provider requests: 12 / 12 authorized.
- Completed schema-valid cases: 11 / 12.
- Provider failures: 0.
- Output failures: 1 (`matcher-dev-008`, `invalid_schema`).
- Provider-reported tokens for the 11 schema-valid responses: 12,801 input and
  2,123 output.
- Token usage for the invalid-schema response was not exposed by the current
  adapter error path, so actual invocation token use is greater than the recorded
  14,924 tokens and is otherwise not measured.
- Mean recorded latency for completed cases: 10,050.8 ms.

The run did not encounter the earlier 8K TPM rate-limit failure. Request pacing
prevented a short-window burst without changing provider or model.

## Quality Result

| Metric | Result | Gate | Status |
|---|---:|---:|---|
| Schema pass | `0.9167` | `1.0000` | Fail |
| Provider failures | `0` | `0` | Pass |
| Output failures | `1` | `0` | Fail |
| Matcher-only verdict accuracy | 8 / 12 (`0.6667`) | at least 10 / 12 | Fail |
| Matcher-only macro-F1 | `0.6810` | at least `0.7500` | Fail |
| Matcher-only acceptable evidence | 5 / 6 (`0.8333`) | `1.0000` | Fail |
| Matcher-only atomic verdict accuracy | 6 / 9 (`0.6667`) | at least 7 / 9 | Fail |
| Matcher-only composite verdict accuracy | 2 / 3 (`0.6667`) | at least 2 / 3 | Pass |
| Citation grounding validity | `1.0000` | `1.0000` | Pass |
| Unsupported-positive rate | `0.0000` | `0.0000` | Pass |
| Every verdict class has non-zero recall | yes | yes | Pass |

Matcher-only recall by expected class:

- `matched`: `1.0000`
- `partial`: `0.5000`
- `missing`: `1.0000`
- `insufficient_evidence`: `0.3333`

## Case Diagnosis

- `matcher-dev-004`: returned `missing`; the Rust future plan requires
  `insufficient_evidence`.
- `matcher-dev-008`: provider output failed the strict response schema. No gap
  verdict was inferred and there was no fake fallback.
- `matcher-dev-009`: returned `insufficient_evidence`; the available keyboard
  navigation implementation supports one separable part, so the candidate-
  conditioned verdict is `partial`.
- `matcher-dev-010`: returned `matched`; the Experience proves offline conflict-
  aware synchronization but not end-to-end encrypted server storage, so the
  verdict must be `partial`.

All five emitted positive citations were grounded and supported the selected
Experience/source. The report's `0.8333` acceptable-evidence score includes the
missing positive selection for `matcher-dev-009`; it is not a grounding failure.

## Decision

The frozen development gates did not pass. This report does not authorize matcher
holdout or production worker integration. The one failed case may be recovered
only through a separately authorized, new immutable report using this report as
`--resume-from`; no recovery request was made in this stage.

ADR-028 later derived 9/12 three-class coverage from this unchanged report. That
offline result is stored separately and does not retroactively change these
original metrics or gate decisions.
