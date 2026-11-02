# Matcher labels, round M2 (80 pairs, 940 requirements)

Pre-registered: committed before any analysis run on these pairs.

- `pair_requirements.json`: the parsed requirements that were labeled (frozen from real parse runs).
- `claude/`: labeler "claude" (4 Claude subagents, one per batch).
- `codex/`: labeler "codex", version 2. `build_m2_v2.py.txt` (Codex's script, stored as text so it is not linted) holds Codex's explicit per-requirement verdict codes.
  Its "missing" rows share one templated rationale and gap code (`required_technology_absent`), so gap reasons
  from this labeler carry little information.
- `codex_rejected_v1/`: Codex's first attempt, rejected before adjudication because its assembler defaulted every
  unlisted requirement to "missing" (agreement 0.817, kappa 0.213 against claude). Kept for transparency only.
- `agreement_codex_vs_claude.json`: agreement 0.870, Cohen's kappa 0.674 (v2).
- `adjudication/`: blinded packets (option order hash-determined, rationales hidden) and the adjudicators' decisions.
- `final/`: merged labels, merge stats, and adjudication direction (labeler_a = codex, labeler_b = claude).
  Even blinded, adjudicators chose the claude verdict 93 of 122 times (codex 26, neither 3).

All labels are model-made, not human ground truth.
