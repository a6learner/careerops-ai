# Matcher labels, round M3 (1 pair, 25 requirements)

Pair `r09-jd-06627db35f`. Its original parse run was left in `running` when the host slept, and the first evaluation
database was deleted before it was resubmitted. It was re-run on a rebuilt stack (same pinned OpenRouter→Groq route)
and these labels were committed before its analysis ran.

- `claude/`, `codex/`: the two independent labelers.
- `agreement_codex_vs_claude.json`: agreement 0.72, Cohen's kappa 0.588 (n = 25, so the interval is wide).
- `adjudication/`: blinded packet (hash-ordered options, rationales hidden) and decisions for the 7 disputes.
- `final/`: merged labels, merge stats and adjudication direction (labeler_a = codex, labeler_b = claude).

All labels are model-made, not human ground truth.
