"""Usage: python -I validate_parser_labels.py <packet.json> <labels.json>"""
import json, sys
packet = {x["jd_id"]: {c["candidate_id"]: c["text"] for c in x["candidates"]} for x in json.load(open(sys.argv[1], encoding="utf-8"))}
labels = json.load(open(sys.argv[2], encoding="utf-8"))
errors = []
seen_jds = set()
for item in labels:
    jd = item.get("jd_id")
    if jd not in packet: errors.append(f"unknown jd_id {jd}"); continue
    seen_jds.add(jd)
    ids = set()
    for r in item.get("requirements", []):
        cid = r.get("candidate_id")
        if packet[jd].get(cid) != r.get("text"): errors.append(f"{jd} cand {cid}: text not identical to candidate")
        if cid in ids: errors.append(f"{jd} cand {cid}: duplicate")
        ids.add(cid)
        if r.get("category") not in {"must_have", "nice_to_have", "responsibility", "education"}: errors.append(f"{jd} cand {cid}: bad category")
        s = r.get("skill_normalized")
        if s is not None and (not isinstance(s, str) or s != s.strip().lower() or not s): errors.append(f"{jd} cand {cid}: skill must be lowercase stripped or null")
    if not item.get("labeler"): errors.append(f"{jd}: missing labeler")
for jd in set(packet) - seen_jds: errors.append(f"missing jd {jd}")
print("OK" if not errors else "\n".join(errors[:50]) + f"\n{len(errors)} errors")
sys.exit(1 if errors else 0)
