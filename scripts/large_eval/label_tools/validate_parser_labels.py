"""Usage: python -I validate_parser_labels.py <packet.json> <labels.json>"""

import json
import sys
from typing import Any

CATEGORIES = {"must_have", "nice_to_have", "responsibility", "education"}


def load_json(path: str) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def check_requirements(jd: str, item: dict[str, Any], packet_texts: dict[Any, str]) -> list[str]:
    errors: list[str] = []
    ids: set[Any] = set()
    for r in item.get("requirements", []):
        cid = r.get("candidate_id")
        if packet_texts.get(cid) != r.get("text"):
            errors.append(f"{jd} cand {cid}: text not identical to candidate")
        if cid in ids:
            errors.append(f"{jd} cand {cid}: duplicate")
        ids.add(cid)
        if r.get("category") not in CATEGORIES:
            errors.append(f"{jd} cand {cid}: bad category")
        s = r.get("skill_normalized")
        if s is not None and (not isinstance(s, str) or s != s.strip().lower() or not s):
            errors.append(f"{jd} cand {cid}: skill must be lowercase stripped or null")
    return errors


def main() -> None:
    packet: dict[str, dict[Any, str]] = {
        x["jd_id"]: {c["candidate_id"]: c["text"] for c in x["candidates"]}
        for x in load_json(sys.argv[1])
    }
    labels = load_json(sys.argv[2])
    errors: list[str] = []
    seen_jds: set[str] = set()
    for item in labels:
        jd = item.get("jd_id")
        if jd not in packet:
            errors.append(f"unknown jd_id {jd}")
            continue
        seen_jds.add(jd)
        errors.extend(check_requirements(jd, item, packet[jd]))
        if not item.get("labeler"):
            errors.append(f"{jd}: missing labeler")
    for jd in set(packet) - seen_jds:
        errors.append(f"missing jd {jd}")
    print("OK" if not errors else "\n".join(errors[:50]) + f"\n{len(errors)} errors")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
