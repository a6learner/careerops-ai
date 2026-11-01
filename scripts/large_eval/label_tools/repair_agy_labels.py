"""Mechanical repair of agy parser labels (decisions untouched).

- Insert commas missing after a "text": "..." line (agy hand-wrote JSON with file tools).
- Replace `text` with the packet's candidate text for the same candidate_id (copy errors).
- Drop requirements whose candidate_id does not exist in the packet.
Every repair is counted in REPAIR_LOG.json.
"""

import json
import re
import sys
from typing import Any

MISSING_COMMA = re.compile(r'("text": "(?:[^"\\]|\\.)*")(\s*\n\s*"category")')


def load_json(path: str) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def repair_requirements(
    item: dict[str, Any], packet_texts: dict[Any, str]
) -> tuple[list[dict[str, Any]], int, int]:
    keep: list[dict[str, Any]] = []
    seen: set[Any] = set()
    text_fixed = dropped = 0
    for req in item["requirements"]:
        truth = packet_texts.get(req["candidate_id"])
        if truth is None or req["candidate_id"] in seen:
            dropped += 1
            continue
        seen.add(req["candidate_id"])
        if req["text"] != truth:
            req["text"] = truth
            text_fixed += 1
        if isinstance(req.get("skill_normalized"), str):
            req["skill_normalized"] = req["skill_normalized"].strip().lower() or None
        keep.append(req)
    return keep, text_fixed, dropped


def repair_batch(root: str, nn: str) -> dict[str, int]:
    with open(f"{root}/labels/parser_agy/parser_labels_{nn}.json", encoding="utf-8") as f:
        raw = f.read()
    fixed, commas = MISSING_COMMA.subn(r"\1,\2", raw)
    data = json.loads(fixed)
    packet_items = load_json(f"{root}/labels/packets/parser_batch_{nn}.json")
    packet = {
        x["jd_id"]: {c["candidate_id"]: c["text"] for c in x["candidates"]} for x in packet_items
    }
    text_fixed = dropped = 0
    for item in data:
        keep, item_fixed, item_dropped = repair_requirements(item, packet[item["jd_id"]])
        item["requirements"] = keep
        text_fixed += item_fixed
        dropped += item_dropped
    out = f"{root}/labels/parser_agy_repaired/parser_labels_{nn}.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    return {
        "missing_commas_inserted": commas,
        "text_replaced_from_candidate_id": text_fixed,
        "unknown_or_duplicate_candidate_dropped": dropped,
    }


def main() -> None:
    root = sys.argv[1]
    log = {f"{n:02d}": repair_batch(root, f"{n:02d}") for n in range(8)}
    with open(f"{root}/labels/parser_agy_repaired/REPAIR_LOG.json", "w") as f:
        json.dump(log, f, indent=1)
    print(json.dumps(log))


if __name__ == "__main__":
    main()
