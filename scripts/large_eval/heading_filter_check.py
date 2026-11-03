"""Check the parse-v4 heading filter against the adjudicated large_scale_v1 parser labels.

Reports how many source candidates the filter removes, how many labeled requirements it would
remove (each one is a lost real requirement), and how many requirements of the 150 analysed pairs
it removes.

Usage:
    python -m scripts.large_eval.heading_filter_check --dataset evals/large_scale_v1 \
        --pair-requirements <pair_requirements_all.json> --out <report.json>
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from careerops.adapters.groq_requirement_parser import extract_source_candidates, is_section_heading
from scripts.large_eval.labels import load_jds, load_parser_labels


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--pair-requirements", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    jds = load_jds(args.dataset)
    labels = load_parser_labels(args.dataset / "labels" / "parser" / "final", jds)
    candidates = removed = labeled = 0
    labeled_removed: list[dict[str, str]] = []
    for jd_id, label in sorted(labels.items()):
        source = extract_source_candidates(jds[jd_id].raw_description)
        headings = {item.candidate_id for item in source if is_section_heading(item.text)}
        candidates += len(source)
        removed += len(headings)
        for requirement in label.requirements:
            labeled += 1
            if requirement.candidate_id in headings:
                labeled_removed.append({"jd_id": jd_id, "text": requirement.text})
    pairs = json.loads(args.pair_requirements.read_text(encoding="utf-8"))
    pair_requirements = [req for pair in pairs for req in pair["requirements"]]
    pair_headings = [req for req in pair_requirements if is_section_heading(req["text"])]
    emptied = [
        pair["pair_id"]
        for pair in pairs
        if all(is_section_heading(req["text"]) for req in pair["requirements"])
    ]
    report = {
        "jds": len(labels),
        "source_candidates": candidates,
        "source_candidates_removed": removed,
        "labeled_requirements": labeled,
        "labeled_requirements_removed": len(labeled_removed),
        "labeled_requirements_removed_detail": labeled_removed,
        "analysed_pair_requirements": len(pair_requirements),
        "analysed_pair_requirements_removed": len(pair_headings),
        "analysed_pair_requirements_removed_texts": sorted({req["text"] for req in pair_headings}),
        "pairs_left_without_requirements": emptied,
    }
    args.out.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if not k.endswith("texts")}, indent=1))


if __name__ == "__main__":
    main()
