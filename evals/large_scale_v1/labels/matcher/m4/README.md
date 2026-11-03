# Matcher labels, round M4 (1 pair, 12 requirements)

Pair `r29-jd-e0e4f3984c`. Its earlier parse attempts all ran before the OpenRouter→Groq pin (4 `PARSER_FAILED` on
the Groq free tier, then 1 `PARSER_OUTPUT_INVALID` under mixed upstream routing), and the driver does not retry
`PARSER_OUTPUT_INVALID`. It was re-parsed on a rebuilt stack on the pinned route, where it succeeded, and these
labels were committed before its analysis ran.

- `claude/`, `codex/`: the two independent labelers.
- `agreement_codex_vs_claude.json`: agreement 0.583, Cohen's kappa 0.394 (n = 12, so the interval is wide).
- `adjudication/`: blinded packet (hash-ordered options, rationales hidden) and decisions for the 5 disputes.
- `final/`: merged labels, merge stats and adjudication direction (labeler_a = codex, labeler_b = claude).

All labels are model-made, not human ground truth.
