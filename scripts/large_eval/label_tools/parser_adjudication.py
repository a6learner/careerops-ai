"""Build adjudication packets for parser-label disagreements, and merge final labels.

build: python -I parser_adjudication.py build <S> <n_packets>
merge: python -I parser_adjudication.py merge <S>
Final label per candidate: if both labelers agree on selection, category and skill -> that;
otherwise the adjudicator's decision. Writes labels/parser_final/parser_labels_NN.json
(labeler "adjudicated").
"""

import glob
import json
import sys
from typing import Any

Labels = dict[str, dict[Any, dict[str, Any]]]
Packets = dict[str, tuple[str, dict[str, Any]]]


def load_json(path: str) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_json(path: str, data: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)


def load(root: str, directory: str) -> Labels:
    out: Labels = {}
    for path in sorted(glob.glob(f"{root}/labels/{directory}/parser_labels_*.json")):
        for item in load_json(path):
            out[item["jd_id"]] = {r["candidate_id"]: r for r in item["requirements"]}
    return out


def packets(root: str) -> Packets:
    out: Packets = {}
    for path in sorted(glob.glob(f"{root}/labels/packets/parser_batch_*.json")):
        nn = path[-7:-5]
        for item in load_json(path):
            out[item["jd_id"]] = (nn, item)
    return out


def agree(ra: dict[str, Any] | None, rb: dict[str, Any] | None) -> bool:
    return bool(
        ra
        and rb
        and ra["category"] == rb["category"]
        and ra["skill_normalized"] == rb["skill_normalized"]
    )


def option(r: dict[str, Any] | None) -> dict[str, Any] | None:
    if r is None:
        return None
    return {"category": r["category"], "skill_normalized": r["skill_normalized"]}


def disagreements(root: str) -> list[dict[str, Any]]:
    a, b, pk = load(root, "parser_codex"), load(root, "parser_agy_repaired"), packets(root)
    items = []
    for jd_id, (_, item) in sorted(pk.items()):
        cands = item["candidates"]
        for c in cands:
            cid = c["candidate_id"]
            ra, rb = a[jd_id].get(cid), b[jd_id].get(cid)
            if ra is None and rb is None:
                continue
            if agree(ra, rb):
                continue
            context = [x["text"] for x in cands[max(0, cid - 4) : cid]]
            items.append(
                {
                    "jd_id": jd_id,
                    "title": item["title"],
                    "candidate_id": cid,
                    "text": c["text"],
                    "preceding_lines": context,
                    "option_a": option(ra),
                    "option_b": option(rb),
                }
            )
    return items


def build(root: str, n: int) -> None:
    items = disagreements(root)
    for i in range(n):
        write_json(f"{root}/labels/adjudication/parser_adj_{i:02d}.json", items[i::n])
    print(f"{len(items)} items in {n} packets")


def load_decisions(root: str) -> dict[tuple[str, Any], dict[str, Any]]:
    decisions = {}
    for path in sorted(glob.glob(f"{root}/labels/adjudication/parser_adj_*_decisions.json")):
        for d in load_json(path):
            decisions[(d["jd_id"], d["candidate_id"])] = d
    return decisions


def normalize_skill(skill: Any) -> str | None:
    return skill.strip().lower() or None if isinstance(skill, str) else None


def merge(root: str) -> None:
    a, b, pk = load(root, "parser_codex"), load(root, "parser_agy_repaired"), packets(root)
    decisions = load_decisions(root)
    batches: dict[str, list[dict[str, Any]]] = {}
    stats = {
        "agreed": 0,
        "adjudicated_selected": 0,
        "adjudicated_rejected": 0,
        "missing_decision": 0,
    }
    for jd_id, (nn, item) in sorted(pk.items()):
        reqs = []
        for c in item["candidates"]:
            cid = c["candidate_id"]
            ra, rb = a[jd_id].get(cid), b[jd_id].get(cid)
            if ra is None and rb is None:
                continue
            if ra is not None and agree(ra, rb):
                stats["agreed"] += 1
                reqs.append(
                    {
                        "candidate_id": cid,
                        "text": c["text"],
                        "category": ra["category"],
                        "skill_normalized": ra["skill_normalized"],
                    }
                )
                continue
            d = decisions.get((jd_id, cid))
            if d is None:
                stats["missing_decision"] += 1
                continue
            if not d["is_requirement"]:
                stats["adjudicated_rejected"] += 1
                continue
            stats["adjudicated_selected"] += 1
            reqs.append(
                {
                    "candidate_id": cid,
                    "text": c["text"],
                    "category": d["category"],
                    "skill_normalized": normalize_skill(d.get("skill_normalized")),
                }
            )
        batches.setdefault(nn, []).append(
            {"jd_id": jd_id, "labeler": "adjudicated", "requirements": reqs}
        )
    for nn, data in batches.items():
        write_json(f"{root}/labels/parser_final/parser_labels_{nn}.json", data)
    with open(f"{root}/labels/parser_final/MERGE_STATS.json", "w") as f:
        json.dump(stats, f, indent=1)
    print(stats)


def main() -> None:
    root = sys.argv[2]
    if sys.argv[1] == "build":
        build(root, int(sys.argv[3]))
    else:
        merge(root)


if __name__ == "__main__":
    main()
