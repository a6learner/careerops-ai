"""Build adjudication packets for parser-label disagreements, and merge final labels.

build: python -I parser_adjudication.py build <S> <n_packets>
merge: python -I parser_adjudication.py merge <S>
Final label per candidate: if both labelers agree on selection, category and skill -> that; otherwise the
adjudicator's decision. Writes labels/parser_final/parser_labels_NN.json (labeler "adjudicated").
"""

import glob
import json
import sys

S = sys.argv[2]


def load(directory):
    out = {}
    for path in sorted(glob.glob(f"{S}/labels/{directory}/parser_labels_*.json")):
        for item in json.load(open(path, encoding="utf-8")):
            out[item["jd_id"]] = {r["candidate_id"]: r for r in item["requirements"]}
    return out


def packets():
    out = {}
    for path in sorted(glob.glob(f"{S}/labels/packets/parser_batch_*.json")):
        nn = path[-7:-5]
        for item in json.load(open(path, encoding="utf-8")):
            out[item["jd_id"]] = (nn, item)
    return out


def disagreements():
    a, b, pk = load("parser_codex"), load("parser_agy_repaired"), packets()
    items = []
    for jd_id, (_, item) in sorted(pk.items()):
        cands = item["candidates"]
        for c in cands:
            cid = c["candidate_id"]
            ra, rb = a[jd_id].get(cid), b[jd_id].get(cid)
            if ra is None and rb is None:
                continue
            if ra and rb and ra["category"] == rb["category"] and ra["skill_normalized"] == rb["skill_normalized"]:
                continue
            context = [x["text"] for x in cands[max(0, cid - 4): cid]]
            items.append({
                "jd_id": jd_id, "title": item["title"], "candidate_id": cid, "text": c["text"],
                "preceding_lines": context,
                "option_a": None if ra is None else {"category": ra["category"], "skill_normalized": ra["skill_normalized"]},
                "option_b": None if rb is None else {"category": rb["category"], "skill_normalized": rb["skill_normalized"]},
            })
    return items


if sys.argv[1] == "build":
    items = disagreements()
    n = int(sys.argv[3])
    for i in range(n):
        json.dump(items[i::n], open(f"{S}/labels/adjudication/parser_adj_{i:02d}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{len(items)} items in {n} packets")
else:
    a, b, pk = load("parser_codex"), load("parser_agy_repaired"), packets()
    decisions = {}
    for path in sorted(glob.glob(f"{S}/labels/adjudication/parser_adj_*_decisions.json")):
        for d in json.load(open(path, encoding="utf-8")):
            decisions[(d["jd_id"], d["candidate_id"])] = d
    batches, stats = {}, {"agreed": 0, "adjudicated_selected": 0, "adjudicated_rejected": 0, "missing_decision": 0}
    for jd_id, (nn, item) in sorted(pk.items()):
        reqs = []
        for c in item["candidates"]:
            cid = c["candidate_id"]
            ra, rb = a[jd_id].get(cid), b[jd_id].get(cid)
            if ra is None and rb is None:
                continue
            if ra and rb and ra["category"] == rb["category"] and ra["skill_normalized"] == rb["skill_normalized"]:
                stats["agreed"] += 1
                reqs.append({"candidate_id": cid, "text": c["text"], "category": ra["category"], "skill_normalized": ra["skill_normalized"]})
                continue
            d = decisions.get((jd_id, cid))
            if d is None:
                stats["missing_decision"] += 1
                continue
            if not d["is_requirement"]:
                stats["adjudicated_rejected"] += 1
                continue
            stats["adjudicated_selected"] += 1
            skill = d.get("skill_normalized")
            skill = skill.strip().lower() or None if isinstance(skill, str) else None
            reqs.append({"candidate_id": cid, "text": c["text"], "category": d["category"], "skill_normalized": skill})
        batches.setdefault(nn, []).append({"jd_id": jd_id, "labeler": "adjudicated", "requirements": reqs})
    for nn, data in batches.items():
        json.dump(data, open(f"{S}/labels/parser_final/parser_labels_{nn}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(stats, open(f"{S}/labels/parser_final/MERGE_STATS.json", "w"), indent=1)
    print(stats)
