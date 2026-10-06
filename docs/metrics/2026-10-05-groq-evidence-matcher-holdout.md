# Groq Evidence Matcher One-Time Holdout

## Scope

This is the immutable evidence record for the first and only matcher holdout
run. The author approved the rubric-v2 manifest before access. Prompt v4,
schema v1, Groq `openai/gpt-oss-20b`, retrieval candidates, coverage evaluator,
and safety policy were frozen before model output was seen.

## Execution

- cases: 8 synthetic holdout cases
- provider attempts: 8
- request slots consumed: 8/8
- resume count: 0
- indeterminate attempts: 0
- provider failures: 0
- output failures: 0
- input tokens: 11,826
- output tokens: 875

The runner used one attempt per case, at least 11 seconds between request starts,
atomic checkpoints, and an immutable final output. No case was repeated.

## Frozen Safety Gates

| Gate | Observed | Required | Result |
|---|---:|---:|---|
| Schema pass | 8/8 | 8/8 | pass |
| Provider failures | 0 | 0 | pass |
| Output failures | 0 | 0 | pass |
| Citation grounding | 1/1 | 100% of positives | pass |
| Unsupported positive | 0/1 | 0 | pass |
| Gap to positive | 0/5 | 0 | pass |
| Partial to matched | 0/2 | 0 | pass |

All pre-frozen evidence-integrity safety gates passed. This authorizes the
separately controlled worker integration; it does not prove production accuracy.

## Quality Diagnostics

- matcher-only coverage: 6/8 (75.0%)
- end-to-end coverage: 5/8 (62.5%)
- four-class exact verdict: 6/8 (75.0%)
- full recall: 1/1
- gap recall: 5/5
- partial recall: 0/2
- `partial -> gap`: 2/2
- matcher-only acceptable evidence: 1/3
- canonical quote exact agreement: 0/3

The model made no measured overclaim, but it missed both partial-evidence
opportunities. This is an important MVP product limitation: the system may fail
to surface a real experience that could strengthen a resume. It is not removed
from any denominator and must not be described as a quality-gate pass.

## Evidence Identity

- manifest SHA-256:
  `099dd7d4eb034284ab2938a83abf111529a5a4ecae65796bcf95b2fe2a5186da`
- checkpoint SHA-256:
  `7ef6f6eeb8729dd10fe86cad791ae21b66097c087bc4350b73cc4450c55c83da`
- final JSON SHA-256:
  `64c8b340375c7f7477b3033c77e2a5048e4614ce11745044c9be9d8ab1c857f7`
- git revision label: `6041cf3-dirty-p1-5-holdout-v2`

Raw evidence:

- `docs/metrics/2026-10-05-groq-evidence-matcher-holdout.json`
- `docs/metrics/2026-10-05-groq-evidence-matcher-holdout-checkpoint.json`

## Limitations

The dataset is small and synthetic. The result is one sample from one model and
does not measure production reliability, user satisfaction, or real-resume
accuracy. The completed holdout is closed: it must not be rerun, relabeled, or
used for prompt or retrieval tuning.
