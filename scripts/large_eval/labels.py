"""Labeling packets, label validation, agreement and adjudication for large_scale_v1.

Commands: parser-packets, parser-agreement, matcher-packets, matcher-agreement.
Run `python -m scripts.large_eval.labels --help` for arguments.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from careerops.adapters.groq_requirement_parser import extract_source_candidates
from scripts.large_eval.models import (
    JdRecord,
    MatcherLabelSet,
    ParserLabelSet,
    ResumeRecord,
)

SOURCE_FIELDS = ("title", "description", "outcome")
GAP_REASONS = (
    "required_technology_absent",
    "future_plan_only",
    "learning_or_discussion_only",
    "explicit_non_implementation",
    "metric_not_proven",
)


def load_jds(dataset: Path) -> dict[str, JdRecord]:
    payload = json.loads((dataset / "jds.json").read_text(encoding="utf-8"))
    return {item["jd_id"]: JdRecord.model_validate(item) for item in payload}


def load_resumes(dataset: Path) -> dict[str, ResumeRecord]:
    payload = json.loads((dataset / "resumes.json").read_text(encoding="utf-8"))
    return {item["resume_id"]: ResumeRecord.model_validate(item) for item in payload}


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def parser_packets(dataset: Path, out: Path, batches: int) -> None:
    jds = sorted(load_jds(dataset).values(), key=lambda jd: jd.jd_id)
    for index in range(batches):
        chunk = jds[index::batches]
        packet = [
            {
                "jd_id": jd.jd_id,
                "company": jd.company,
                "title": jd.title,
                "candidates": [
                    {"candidate_id": c.candidate_id, "text": c.text}
                    for c in extract_source_candidates(jd.raw_description)
                ],
            }
            for jd in chunk
        ]
        write_json(out / f"parser_batch_{index:02d}.json", packet)
    print(f"wrote {batches} parser packets for {len(jds)} JDs")


def load_parser_labels(directory: Path, jds: dict[str, JdRecord]) -> dict[str, ParserLabelSet]:
    labels: dict[str, ParserLabelSet] = {}
    for path in sorted(directory.glob("parser_labels_*.json")):
        for item in json.loads(path.read_text(encoding="utf-8")):
            label = ParserLabelSet.model_validate(item)
            validate_parser_label(label, jds[label.jd_id])
            labels[label.jd_id] = label
    return labels


def validate_parser_label(label: ParserLabelSet, jd: JdRecord) -> None:
    candidates = {c.candidate_id: c.text for c in extract_source_candidates(jd.raw_description)}
    seen: set[int] = set()
    for requirement in label.requirements:
        if candidates.get(requirement.candidate_id) != requirement.text:
            raise ValueError(f"{label.jd_id}: candidate {requirement.candidate_id} text mismatch")
        if requirement.candidate_id in seen:
            raise ValueError(f"{label.jd_id}: duplicate candidate {requirement.candidate_id}")
        if requirement.skill_normalized is not None and (
            requirement.skill_normalized != requirement.skill_normalized.strip().casefold()
        ):
            raise ValueError(f"{label.jd_id}: skill must be lowercase and stripped")
        seen.add(requirement.candidate_id)


def cohen_kappa(pairs: list[tuple[str, str]]) -> float | None:
    if not pairs:
        return None
    observed = sum(a == b for a, b in pairs) / len(pairs)
    left = Counter(a for a, _ in pairs)
    right = Counter(b for _, b in pairs)
    expected = sum(left[k] * right[k] for k in left) / (len(pairs) ** 2)
    return None if expected == 1 else (observed - expected) / (1 - expected)


def parser_agreement(dataset: Path, a: Path, b: Path, out: Path) -> None:
    jds = load_jds(dataset)
    left = load_parser_labels(a, jds)
    right = load_parser_labels(b, jds)
    selection: list[tuple[str, str]] = []
    category: list[tuple[str, str]] = []
    skill_agree = skill_total = 0
    disagreements: list[dict[str, Any]] = []
    for jd_id in sorted(set(left) & set(right)):
        la = {r.candidate_id: r for r in left[jd_id].requirements}
        lb = {r.candidate_id: r for r in right[jd_id].requirements}
        for candidate in extract_source_candidates(jds[jd_id].raw_description):
            cid = candidate.candidate_id
            in_a, in_b = cid in la, cid in lb
            selection.append((str(in_a), str(in_b)))
            if in_a and in_b:
                category.append((la[cid].category, lb[cid].category))
                skill_total += 1
                skill_agree += la[cid].skill_normalized == lb[cid].skill_normalized
                if la[cid].category != lb[cid].category:
                    disagreements.append(
                        {
                            "jd_id": jd_id,
                            "candidate_id": cid,
                            "kind": "category",
                            "a": la[cid].category,
                            "b": lb[cid].category,
                            "text": candidate.text,
                        }
                    )
            elif in_a != in_b:
                disagreements.append(
                    {
                        "jd_id": jd_id,
                        "candidate_id": cid,
                        "kind": "selection",
                        "a": in_a,
                        "b": in_b,
                        "text": candidate.text,
                    }
                )
    report = {
        "jd_count_both": len(set(left) & set(right)),
        "missing_in_a": sorted(set(right) - set(left)),
        "missing_in_b": sorted(set(left) - set(right)),
        "candidate_count": len(selection),
        "selection_agreement": sum(x == y for x, y in selection) / max(len(selection), 1),
        "selection_kappa": cohen_kappa(selection),
        "category_pairs": len(category),
        "category_agreement": sum(x == y for x, y in category) / max(len(category), 1),
        "category_kappa": cohen_kappa(category),
        "skill_exact_agreement": skill_agree / max(skill_total, 1),
        "disagreement_count": len(disagreements),
        "disagreements": disagreements,
    }
    write_json(out, report)
    print(json.dumps({k: v for k, v in report.items() if k != "disagreements"}, indent=1))


def experience_sources(resume: ResumeRecord) -> list[dict[str, Any]]:
    return [
        {
            "exp_key": exp.exp_key,
            "kind": exp.kind,
            "title": exp.title,
            "description": exp.description,
            "skills": list(exp.skills),
            "outcome": exp.outcome,
        }
        for exp in resume.experiences
    ]


def matcher_packets(dataset: Path, requirements: Path, out: Path, batches: int) -> None:
    resumes = load_resumes(dataset)
    pairs = json.loads(requirements.read_text(encoding="utf-8"))
    for index in range(batches):
        packet = [
            {
                "pair_id": pair["pair_id"],
                "resume_id": pair["resume_id"],
                "experiences": experience_sources(resumes[pair["resume_id"]]),
                "requirements": pair["requirements"],
            }
            for pair in pairs[index::batches]
        ]
        write_json(out / f"matcher_batch_{index:02d}.json", packet)
    print(f"wrote {batches} matcher packets for {len(pairs)} pairs")


def source_text(resume: ResumeRecord, exp_key: str, source_ref: str) -> str:
    exp = next(e for e in resume.experiences if e.exp_key == exp_key)
    if source_ref.startswith("skill:"):
        return exp.skills[int(source_ref.split(":", 1)[1])]
    value = getattr(exp, source_ref)
    return "" if value is None else str(value)


def load_matcher_labels(
    directory: Path, resumes: dict[str, ResumeRecord], pairs: dict[str, dict[str, Any]]
) -> dict[str, MatcherLabelSet]:
    labels: dict[str, MatcherLabelSet] = {}
    for path in sorted(directory.glob("matcher_labels_*.json")):
        for item in json.loads(path.read_text(encoding="utf-8")):
            label = MatcherLabelSet.model_validate(item)
            pair = pairs[label.pair_id]
            resume = resumes[pair["resume_id"]]
            expected = {r["requirement_id"] for r in pair["requirements"]}
            got = [entry.requirement_id for entry in label.labels]
            if set(got) != expected or len(got) != len(expected):
                raise ValueError(f"{label.pair_id}: labels must cover each requirement once")
            for entry in label.labels:
                positive = entry.verdict in {"matched", "partial"}
                if positive and not entry.evidence:
                    raise ValueError(
                        f"{label.pair_id}/{entry.requirement_id}: positive needs evidence"
                    )
                if not positive and entry.gap_reason_code not in GAP_REASONS:
                    raise ValueError(f"{label.pair_id}/{entry.requirement_id}: bad gap reason")
                for evidence in entry.evidence:
                    if evidence.quote not in source_text(
                        resume, evidence.exp_key, evidence.source_ref
                    ):
                        raise ValueError(
                            f"{label.pair_id}/{entry.requirement_id}: ungrounded quote"
                        )
            labels[label.pair_id] = label
    return labels


def matcher_agreement(dataset: Path, requirements: Path, a: Path, b: Path, out: Path) -> None:
    resumes = load_resumes(dataset)
    pairs = {p["pair_id"]: p for p in json.loads(requirements.read_text(encoding="utf-8"))}
    left = load_matcher_labels(a, resumes, pairs)
    right = load_matcher_labels(b, resumes, pairs)
    verdicts: list[tuple[str, str]] = []
    disagreements: list[dict[str, Any]] = []
    for pair_id in sorted(set(left) & set(right)):
        la = {x.requirement_id: x for x in left[pair_id].labels}
        lb = {x.requirement_id: x for x in right[pair_id].labels}
        for requirement_id, entry in la.items():
            other = lb[requirement_id]
            verdicts.append((entry.verdict, other.verdict))
            if entry.verdict != other.verdict:
                disagreements.append(
                    {
                        "pair_id": pair_id,
                        "requirement_id": requirement_id,
                        "a": entry.verdict,
                        "b": other.verdict,
                    }
                )
    report = {
        "pair_count_both": len(set(left) & set(right)),
        "missing_in_a": sorted(set(pairs) - set(left)),
        "missing_in_b": sorted(set(pairs) - set(right)),
        "requirement_count": len(verdicts),
        "verdict_agreement": sum(x == y for x, y in verdicts) / max(len(verdicts), 1),
        "verdict_kappa": cohen_kappa(verdicts),
        "confusion_a_vs_b": dict(Counter(f"{x}->{y}" for x, y in verdicts)),
        "disagreement_count": len(disagreements),
        "disagreements": disagreements,
    }
    write_json(out, report)
    print(json.dumps({k: v for k, v in report.items() if k != "disagreements"}, indent=1))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        choices=["parser-packets", "parser-agreement", "matcher-packets", "matcher-agreement"],
    )
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--batches", type=int, default=6)
    parser.add_argument("--requirements", type=Path)
    parser.add_argument("--a", type=Path)
    parser.add_argument("--b", type=Path)
    args = parser.parse_args()
    if args.command == "parser-packets":
        parser_packets(args.dataset, args.out, args.batches)
    elif args.command == "parser-agreement":
        parser_agreement(args.dataset, args.a, args.b, args.out)
    elif args.command == "matcher-packets":
        matcher_packets(args.dataset, args.requirements, args.out, args.batches)
    else:
        matcher_agreement(args.dataset, args.requirements, args.a, args.b, args.out)


if __name__ == "__main__":
    main()
