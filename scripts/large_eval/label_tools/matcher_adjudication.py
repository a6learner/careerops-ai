"""Matcher-label adjudication packets and final merge (round-aware).

build: python -I matcher_adjudication.py build <S> <round> <labeler_a_dir> <labeler_b_dir> <n>
merge: python -I matcher_adjudication.py merge <S> <round> <labeler_a_dir> <labeler_b_dir>
Agreement on verdict -> final = that verdict; positive evidence = union of both labelers'
grounded evidence; gap reason from labeler A. Disagreement -> adjudicator decision
(verdict, evidence, gap_reason_code).
"""

import glob
import json
import sys
from typing import Any

Labels = dict[str, dict[str, dict[str, Any]]]
POSITIVE = ("matched", "partial")
DISPUTE_FIELDS = ("verdict", "evidence", "gap_reason_code", "rationale")


def load_json(path: str) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load(root: str, rnd: str, directory: str) -> Labels:
    out: Labels = {}
    for path in sorted(glob.glob(f"{root}/labels/{directory}/matcher_labels_{rnd}_*.json")):
        for pair in load_json(path):
            out[pair["pair_id"]] = {lab["requirement_id"]: lab for lab in pair["labels"]}
    return out


def packets(root: str, rnd: str) -> dict[str, dict[str, Any]]:
    out = {}
    for path in sorted(glob.glob(f"{root}/labels/matcher_packets_{rnd}/matcher_batch_*.json")):
        for pair in load_json(path):
            out[pair["pair_id"]] = pair
    return out


def strip(label: dict[str, Any]) -> dict[str, Any]:
    return {k: label.get(k) for k in DISPUTE_FIELDS}


def build(
    root: str, rnd: str, a: Labels, b: Labels, pk: dict[str, dict[str, Any]], n: int
) -> None:
    items = []
    for pid, pair in sorted(pk.items()):
        dis = []
        for req in pair["requirements"]:
            la, lb = a[pid][req["requirement_id"]], b[pid][req["requirement_id"]]
            if la["verdict"] != lb["verdict"]:
                dis.append({"requirement": req, "option_a": strip(la), "option_b": strip(lb)})
        if dis:
            items.append(
                {
                    "pair_id": pid,
                    "resume_id": pair["resume_id"],
                    "experiences": pair["experiences"],
                    "disputed": dis,
                }
            )
    for i in range(n):
        path = f"{root}/labels/adjudication/matcher_adj_{rnd}_{i:02d}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(items[i::n], f, ensure_ascii=False, indent=1)
    disputed = sum(len(x["disputed"]) for x in items)
    print(f"{disputed} disputed labels in {len(items)} pairs -> {n} packets")


def union_evidence(la: dict[str, Any], lb: dict[str, Any]) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    seen: set[tuple[Any, Any, Any]] = set()
    for e in (la.get("evidence") or []) + (lb.get("evidence") or []):
        key = (e["exp_key"], e["source_ref"], e["quote"])
        if key not in seen:
            seen.add(key)
            evidence.append(e)
    return evidence


def agreed_label(rid: str, la: dict[str, Any], lb: dict[str, Any]) -> dict[str, Any]:
    evidence = union_evidence(la, lb) if la["verdict"] in POSITIVE else []
    return {
        "requirement_id": rid,
        "verdict": la["verdict"],
        "evidence": evidence,
        "gap_reason_code": None if evidence else la.get("gap_reason_code"),
        "rationale": "agreed",
    }


def adjudicated_label(rid: str, d: dict[str, Any]) -> dict[str, Any]:
    positive = d["verdict"] in POSITIVE
    return {
        "requirement_id": rid,
        "verdict": d["verdict"],
        "evidence": (d.get("evidence") or []) if positive else [],
        "gap_reason_code": None if positive else d.get("gap_reason_code"),
        "rationale": "adjudicated: " + (d.get("rationale") or ""),
    }


def merge(root: str, rnd: str, a: Labels, b: Labels, pk: dict[str, dict[str, Any]]) -> None:
    decisions = {}
    pattern = f"{root}/labels/adjudication/matcher_adj_{rnd}_*_decisions.json"
    for path in sorted(glob.glob(pattern)):
        for d in load_json(path):
            decisions[(d["pair_id"], d["requirement_id"])] = d
    final = []
    stats = {"agreed": 0, "adjudicated": 0, "missing_decision": 0}
    for pid, pair in sorted(pk.items()):
        labels = []
        for req in pair["requirements"]:
            rid = req["requirement_id"]
            la, lb = a[pid][rid], b[pid][rid]
            if la["verdict"] == lb["verdict"]:
                stats["agreed"] += 1
                labels.append(agreed_label(rid, la, lb))
                continue
            d = decisions.get((pid, rid))
            if d is None:
                stats["missing_decision"] += 1
                continue
            stats["adjudicated"] += 1
            labels.append(adjudicated_label(rid, d))
        final.append({"pair_id": pid, "labeler": "adjudicated", "labels": labels})
    path = f"{root}/labels/matcher_final/matcher_labels_{rnd}_all.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(final, f, ensure_ascii=False, indent=1)
    with open(f"{root}/labels/matcher_final/MERGE_STATS_{rnd}.json", "w") as f:
        json.dump(stats, f, indent=1)
    print(stats)


def main() -> None:
    cmd, root, rnd, dir_a, dir_b = sys.argv[1:6]
    a, b, pk = load(root, rnd, dir_a), load(root, rnd, dir_b), packets(root, rnd)
    if cmd == "build":
        build(root, rnd, a, b, pk, int(sys.argv[6]))
    else:
        merge(root, rnd, a, b, pk)


if __name__ == "__main__":
    main()
