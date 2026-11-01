"""Matcher-label adjudication packets and final merge (round-aware).

build: python -I matcher_adjudication.py build <S> <round> <labeler_a_dir> <labeler_b_dir> <n_packets>
merge: python -I matcher_adjudication.py merge <S> <round> <labeler_a_dir> <labeler_b_dir>
Agreement on verdict -> final = that verdict; positive evidence = union of both labelers' grounded evidence;
gap reason from labeler A. Disagreement -> adjudicator decision (verdict, evidence, gap_reason_code).
"""

import glob
import json
import sys

cmd, S, RND, A, B = sys.argv[1:6]


def load(directory):
    out = {}
    for path in sorted(glob.glob(f"{S}/labels/{directory}/matcher_labels_{RND}_*.json")):
        for pair in json.load(open(path, encoding="utf-8")):
            out[pair["pair_id"]] = {lab["requirement_id"]: lab for lab in pair["labels"]}
    return out


def packets():
    out = {}
    for path in sorted(glob.glob(f"{S}/labels/matcher_packets_{RND}/matcher_batch_*.json")):
        for pair in json.load(open(path, encoding="utf-8")):
            out[pair["pair_id"]] = pair
    return out


a, b, pk = load(A), load(B), packets()
if cmd == "build":
    n = int(sys.argv[6])
    items = []
    for pid, pair in sorted(pk.items()):
        dis = []
        for req in pair["requirements"]:
            la, lb = a[pid][req["requirement_id"]], b[pid][req["requirement_id"]]
            if la["verdict"] != lb["verdict"]:
                strip = lambda x: {k: x.get(k) for k in ("verdict", "evidence", "gap_reason_code", "rationale")}
                dis.append({"requirement": req, "option_a": strip(la), "option_b": strip(lb)})
        if dis:
            items.append({"pair_id": pid, "resume_id": pair["resume_id"], "experiences": pair["experiences"], "disputed": dis})
    for i in range(n):
        json.dump(items[i::n], open(f"{S}/labels/adjudication/matcher_adj_{RND}_{i:02d}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{sum(len(x['disputed']) for x in items)} disputed labels in {len(items)} pairs -> {n} packets")
else:
    decisions = {}
    for path in sorted(glob.glob(f"{S}/labels/adjudication/matcher_adj_{RND}_*_decisions.json")):
        for d in json.load(open(path, encoding="utf-8")):
            decisions[(d["pair_id"], d["requirement_id"])] = d
    final, stats = [], {"agreed": 0, "adjudicated": 0, "missing_decision": 0}
    for pid, pair in sorted(pk.items()):
        labels = []
        for req in pair["requirements"]:
            rid = req["requirement_id"]
            la, lb = a[pid][rid], b[pid][rid]
            if la["verdict"] == lb["verdict"]:
                stats["agreed"] += 1
                evidence = []
                if la["verdict"] in ("matched", "partial"):
                    seen = set()
                    for e in (la.get("evidence") or []) + (lb.get("evidence") or []):
                        key = (e["exp_key"], e["source_ref"], e["quote"])
                        if key not in seen:
                            seen.add(key)
                            evidence.append(e)
                labels.append({"requirement_id": rid, "verdict": la["verdict"], "evidence": evidence,
                               "gap_reason_code": None if evidence else la.get("gap_reason_code"),
                               "rationale": "agreed"})
                continue
            d = decisions.get((pid, rid))
            if d is None:
                stats["missing_decision"] += 1
                continue
            stats["adjudicated"] += 1
            positive = d["verdict"] in ("matched", "partial")
            labels.append({"requirement_id": rid, "verdict": d["verdict"],
                           "evidence": d.get("evidence") or [] if positive else [],
                           "gap_reason_code": None if positive else d.get("gap_reason_code"),
                           "rationale": "adjudicated: " + (d.get("rationale") or "")})
        final.append({"pair_id": pid, "labeler": "adjudicated", "labels": labels})
    json.dump(final, open(f"{S}/labels/matcher_final/matcher_labels_{RND}_all.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(stats, open(f"{S}/labels/matcher_final/MERGE_STATS_{RND}.json", "w"), indent=1)
    print(stats)
