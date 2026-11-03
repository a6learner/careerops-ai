"""Usage: python -I validate_matcher_labels.py <matcher_batch.json> <matcher_labels.json>"""

import json
import sys
from typing import Any

VERDICTS = {"matched", "partial", "insufficient_evidence", "missing"}
GAPS = {
    "required_technology_absent",
    "future_plan_only",
    "learning_or_discussion_only",
    "explicit_non_implementation",
    "metric_not_proven",
}


def load_json(path: str) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def field(exp: dict[str, Any], ref: str) -> Any:
    if ref.startswith("skill:"):
        i = int(ref.split(":")[1])
        return exp["skills"][i] if i < len(exp["skills"]) else None
    return exp.get(ref) if ref in ("title", "description", "outcome") else None


def check_evidence(
    where: str, evidence: list[dict[str, Any]], exps: dict[Any, dict[str, Any]]
) -> list[str]:
    errors: list[str] = []
    for e in evidence:
        exp = exps.get(e.get("exp_key"))
        text = field(exp, e.get("source_ref", "")) if exp else None
        if text is None:
            errors.append(
                f"{where}: bad exp_key/source_ref {e.get('exp_key')}/{e.get('source_ref')}"
            )
        elif not e.get("quote") or e["quote"] not in text:
            errors.append(
                f"{where}: quote is not an exact substring of {e['exp_key']}.{e['source_ref']}"
            )
    return errors


def check_label(where: str, label: dict[str, Any], exps: dict[Any, dict[str, Any]]) -> list[str]:
    v = label.get("verdict")
    if v not in VERDICTS:
        return [f"{where}: bad verdict"]
    errors: list[str] = []
    ev = label.get("evidence") or []
    if v in ("matched", "partial"):
        if not ev:
            errors.append(f"{where}: positive verdict needs evidence")
        if label.get("gap_reason_code") is not None:
            errors.append(f"{where}: positive must have gap_reason_code null")
    else:
        if ev:
            errors.append(f"{where}: gap verdict must have no evidence")
        if label.get("gap_reason_code") not in GAPS:
            errors.append(f"{where}: bad gap_reason_code")
    errors.extend(check_evidence(where, ev, exps))
    return errors


def main() -> None:
    packet: dict[str, dict[str, Any]] = {p["pair_id"]: p for p in load_json(sys.argv[1])}
    labels = load_json(sys.argv[2])
    errors: list[str] = []
    seen: set[str] = set()
    for item in labels:
        pid = item.get("pair_id")
        p = packet.get(pid)
        if p is None:
            errors.append(f"unknown pair {pid}")
            continue
        seen.add(pid)
        exps = {e["exp_key"]: e for e in p["experiences"]}
        want = {r["requirement_id"] for r in p["requirements"]}
        got = [label.get("requirement_id") for label in item.get("labels", [])]
        if set(got) != want or len(got) != len(want):
            errors.append(f"{pid}: must label each requirement exactly once")
        for label in item.get("labels", []):
            errors.extend(check_label(f"{pid}/{label.get('requirement_id')}", label, exps))
    for pid in set(packet) - seen:
        errors.append(f"missing pair {pid}")
    print("OK" if not errors else "\n".join(errors[:60]) + f"\n{len(errors)} errors")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
