"""Usage: python -I validate_matcher_labels.py <matcher_batch.json> <matcher_labels.json>"""
import json, sys
VERDICTS = {"matched", "partial", "insufficient_evidence", "missing"}
GAPS = {"required_technology_absent", "future_plan_only", "learning_or_discussion_only", "explicit_non_implementation", "metric_not_proven"}
packet = {p["pair_id"]: p for p in json.load(open(sys.argv[1], encoding="utf-8"))}
labels = json.load(open(sys.argv[2], encoding="utf-8"))
errors, seen = [], set()
def field(exp, ref):
    if ref.startswith("skill:"):
        i = int(ref.split(":")[1]); return exp["skills"][i] if i < len(exp["skills"]) else None
    return exp.get(ref) if ref in ("title", "description", "outcome") else None
for item in labels:
    pid = item.get("pair_id"); p = packet.get(pid)
    if p is None: errors.append(f"unknown pair {pid}"); continue
    seen.add(pid)
    exps = {e["exp_key"]: e for e in p["experiences"]}
    want = {r["requirement_id"] for r in p["requirements"]}
    got = [l.get("requirement_id") for l in item.get("labels", [])]
    if set(got) != want or len(got) != len(want): errors.append(f"{pid}: must label each requirement exactly once")
    for l in item.get("labels", []):
        v = l.get("verdict"); rid = l.get("requirement_id")
        if v not in VERDICTS: errors.append(f"{pid}/{rid}: bad verdict"); continue
        ev = l.get("evidence") or []
        if v in ("matched", "partial"):
            if not ev: errors.append(f"{pid}/{rid}: positive verdict needs evidence")
            if l.get("gap_reason_code") is not None: errors.append(f"{pid}/{rid}: positive must have gap_reason_code null")
        else:
            if ev: errors.append(f"{pid}/{rid}: gap verdict must have no evidence")
            if l.get("gap_reason_code") not in GAPS: errors.append(f"{pid}/{rid}: bad gap_reason_code")
        for e in ev:
            exp = exps.get(e.get("exp_key"))
            text = field(exp, e.get("source_ref", "")) if exp else None
            if text is None: errors.append(f"{pid}/{rid}: bad exp_key/source_ref {e.get('exp_key')}/{e.get('source_ref')}")
            elif not e.get("quote") or e["quote"] not in text: errors.append(f"{pid}/{rid}: quote is not an exact substring of {e['exp_key']}.{e['source_ref']}")
for pid in set(packet) - seen: errors.append(f"missing pair {pid}")
print("OK" if not errors else "\n".join(errors[:60]) + f"\n{len(errors)} errors"); sys.exit(1 if errors else 0)
