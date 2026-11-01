"""Mechanical repair of agy parser labels (decisions untouched).

- Insert commas missing after a "text": "..." line (agy hand-wrote JSON with file tools).
- Replace `text` with the packet's candidate text for the same candidate_id (copy errors).
- Drop requirements whose candidate_id does not exist in the packet.
Every repair is counted in REPAIR_LOG.json.
"""

import json
import re
import sys

S = sys.argv[1]
MISSING_COMMA = re.compile(r'("text": "(?:[^"\\]|\\.)*")(\s*\n\s*"category")')
log = {}
for n in range(8):
    nn = f"{n:02d}"
    raw = open(f"{S}/labels/parser_agy/parser_labels_{nn}.json", encoding="utf-8").read()
    fixed, commas = MISSING_COMMA.subn(r"\1,\2", raw)
    data = json.loads(fixed)
    packet_items = json.load(open(f"{S}/labels/packets/parser_batch_{nn}.json", encoding="utf-8"))
    packet = {x["jd_id"]: {c["candidate_id"]: c["text"] for c in x["candidates"]} for x in packet_items}
    text_fixed = dropped = 0
    for item in data:
        keep = []
        seen = set()
        for req in item["requirements"]:
            truth = packet[item["jd_id"]].get(req["candidate_id"])
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
        item["requirements"] = keep
    out = f"{S}/labels/parser_agy_repaired/parser_labels_{nn}.json"
    json.dump(data, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    log[nn] = {
        "missing_commas_inserted": commas,
        "text_replaced_from_candidate_id": text_fixed,
        "unknown_or_duplicate_candidate_dropped": dropped,
    }
json.dump(log, open(f"{S}/labels/parser_agy_repaired/REPAIR_LOG.json", "w"), indent=1)
print(json.dumps(log))
