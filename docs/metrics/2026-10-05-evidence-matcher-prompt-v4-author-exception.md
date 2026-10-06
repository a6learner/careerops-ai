# Prompt V4 Author Policy Exception

## Decision

After reviewing the immutable prompt-v4 development result, the project author
accepted prompt v4 as the frozen matcher holdout candidate with one measured
conservative limitation.

The observed development result remains:

- matcher-only coverage: 11/12;
- four-class exact verdict: 9/12;
- coverage overclaim: 0/12;
- `gap -> positive`: 0/6;
- `partial -> matched`: 0/4;
- `partial -> gap`: 1/4;
- citation grounding: 5/5 emitted positives;
- unsupported positive: 0/5;
- matcher-only acceptable evidence: 5/6.

The original `evidence-matcher-development-gates-v4` outcome remains safety pass,
quality fail. This record does not modify that report and does not claim the
strict quality gate passed.

## Policy Boundary

Policy override `author-accepted-prompt-v4-underclaim-2026-10-05` treats the
observed `partial -> gap` as an accepted MVP underclaim: it can hide a real
resume-strengthening opportunity but cannot create an unsupported claim. Safety
gates remain unchanged. No more development prompt, label, evaluator, or retrieval
tuning is allowed.

This decision authorizes holdout readiness work only. It does not authorize a
provider call, repeat development run, production worker integration, commit, or
push.

## Evidence

- raw report SHA-256:
  `e944c4a08e99b51823ab03da183ad63012d26cba48a5c4d701a28303d0cf7063`
- coverage/gates report SHA-256:
  `706062e5972e202a7d6060c9893caa5cfef203654b298b6265504392824d561f`
- selected development manifest SHA-256:
  `8f05a74d9a9447c7e8588ae3a121288213717b26f2a2141b898d79a7ff4a58cb`

No provider request was made to create this decision record.
