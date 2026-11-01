"""Score large_scale_v1 results. Every rate carries n and a 95% Wilson interval.

Definitions follow ADR-027/ADR-028: matched -> full, partial -> partial,
insufficient_evidence/missing -> gap. Overclaim = gap->partial, gap->full, partial->full.
Underclaim = partial->gap, full->partial, full->gap. Failed runs are never counted as gaps.

Usage:
    python -m scripts.large_eval.score --dataset evals/large_scale_v1 --results <results.json> \
        --parser-labels <dir> --matcher-labels <dir> --requirements <file> \
        --cv-import-state <state.jsonl> --out <metrics.json>
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import Counter
from pathlib import Path
from typing import Any

from scripts.large_eval.drive_pipeline import State
from scripts.large_eval.labels import (
    load_jds,
    load_matcher_labels,
    load_parser_labels,
    load_resumes,
)

COVERAGE = {
    "matched": "full",
    "partial": "partial",
    "insufficient_evidence": "gap",
    "missing": "gap",
}
OVERCLAIM = {("gap", "partial"), ("gap", "full"), ("partial", "full")}
UNDERCLAIM = {("partial", "gap"), ("full", "partial"), ("full", "gap")}
BUCKETS = ((1, 5), (6, 10), (11, 15), (16, 20), (21, 1000))


def wilson(successes: int, n: int) -> dict[str, Any]:
    if n == 0:
        return {"k": 0, "n": 0, "rate": None, "ci95": None}
    z = 1.96
    p = successes / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return {
        "k": successes,
        "n": n,
        "rate": round(p, 4),
        "ci95": [round(max(0.0, centre - half), 4), round(min(1.0, centre + half), 4)],
    }


def percentiles(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"n": 0}
    ordered = sorted(values)

    def pick(q: float) -> float:
        return ordered[min(len(ordered) - 1, max(0, math.ceil(q * len(ordered)) - 1))]

    return {
        "n": len(ordered),
        "p50": pick(0.5),
        "p95": pick(0.95),
        "min": ordered[0],
        "max": ordered[-1],
        "mean": round(statistics.fmean(ordered), 1),
    }


def bucket(count: int) -> str:
    for low, high in BUCKETS:
        if low <= count <= high:
            return f"{low}-{high}" if high < 1000 else f"{low}+"
    return "0"


def succeeded_parse(job: dict[str, Any]) -> dict[str, Any] | None:
    for run in job["parse_runs"]:
        if run["status"] == "succeeded":
            return dict(run)
    return None


def score_parser(dataset: Path, results: dict[str, Any], labels_dir: Path | None) -> dict[str, Any]:
    jobs = results["jobs"]
    first_ok = runs_total = 0
    errors: Counter[str] = Counter()
    final_ok = 0
    req_counts: list[float] = []
    latencies: list[float] = []
    tokens_in: list[float] = []
    tokens_out: list[float] = []
    for job in jobs.values():
        runs = job["parse_runs"]
        if not runs:
            continue
        runs_total += 1
        first = runs[0]
        first_ok += first["status"] == "succeeded"
        for run in runs:
            if run["status"] == "failed":
                errors[str(run["error_code"])] += 1
            if run["input_tokens"] is not None:
                tokens_in.append(float(run["input_tokens"]))
                tokens_out.append(float(run["output_tokens"] or 0))
        ok = succeeded_parse(job)
        if ok is not None:
            final_ok += 1
            req_counts.append(float(len(ok["requirements"])))
            if ok["latency_ms"] is not None:
                latencies.append(float(ok["latency_ms"]))
    report: dict[str, Any] = {
        "jobs_with_parse": runs_total,
        "first_attempt_success": wilson(first_ok, runs_total),
        "final_success_after_rate_limit_retries": wilson(final_ok, runs_total),
        "failed_run_error_codes": dict(errors),
        "requirements_per_successful_parse": percentiles(req_counts),
        "latency_ms_successful": percentiles(latencies),
        "input_tokens_per_run": percentiles(tokens_in),
        "output_tokens_per_run": percentiles(tokens_out),
    }
    if labels_dir is not None:
        report["against_labels"] = parser_against_labels(dataset, jobs, labels_dir)
    report["determinism"] = parser_determinism(jobs)
    return report


def parser_against_labels(dataset: Path, jobs: dict[str, Any], labels_dir: Path) -> dict[str, Any]:
    labels = load_parser_labels(labels_dir, load_jds(dataset))
    tp = predicted = expected = 0
    category_ok = skill_ok = 0
    per_category_expected: Counter[str] = Counter()
    per_category_found: Counter[str] = Counter()
    scored = 0
    for job in jobs.values():
        label = labels.get(job["jd_id"])
        ok = succeeded_parse(job)
        if label is None or ok is None:
            continue
        scored += 1
        got = {req["text"]: req for req in ok["requirements"]}
        want = {req.text: req for req in label.requirements}
        predicted += len(got)
        expected += len(want)
        for text_value, req in want.items():
            per_category_expected[req.category] += 1
            if text_value in got:
                tp += 1
                per_category_found[req.category] += 1
                category_ok += got[text_value]["category"] == req.category
                skill_ok += got[text_value]["skill_normalized"] == req.skill_normalized
    precision = tp / predicted if predicted else None
    recall = tp / expected if expected else None
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision is not None and recall is not None and precision + recall
        else None
    )
    return {
        "jds_scored": scored,
        "labeled_requirements": expected,
        "predicted_requirements": predicted,
        "text_matches": tp,
        "precision": wilson(tp, predicted),
        "recall": wilson(tp, expected),
        "f1": None if f1 is None else round(f1, 4),
        "category_accuracy_on_matches": wilson(category_ok, tp),
        "skill_exact_accuracy_on_matches": wilson(skill_ok, tp),
        "recall_by_label_category": {
            category: wilson(per_category_found[category], count)
            for category, count in sorted(per_category_expected.items())
        },
    }


def parser_determinism(jobs: dict[str, Any]) -> dict[str, Any]:
    by_jd: dict[str, list[set[str]]] = {}
    for job in jobs.values():
        ok = succeeded_parse(job)
        if ok is not None:
            by_jd.setdefault(job["jd_id"], []).append({req["text"] for req in ok["requirements"]})
    repeats = {jd: sets for jd, sets in by_jd.items() if len(sets) >= 2}
    jaccards = [
        len(sets[0] & sets[1]) / max(len(sets[0] | sets[1]), 1) for sets in repeats.values()
    ]
    count_diffs = [abs(len(sets[0]) - len(sets[1])) for sets in repeats.values()]
    return {
        "jds_with_two_successful_parses": len(repeats),
        "text_set_jaccard": percentiles(jaccards),
        "abs_requirement_count_difference": percentiles([float(x) for x in count_diffs]),
        "identical_text_sets": wilson(sum(j == 1.0 for j in jaccards), len(jaccards)),
    }


def score_matcher(
    dataset: Path,
    results: dict[str, Any],
    labels_dir: Path | None,
    requirements_file: Path | None,
) -> dict[str, Any]:
    jobs = {
        key: job for key, job in results["jobs"].items() if not key.startswith("job:parser_only")
    }
    first_status: Counter[str] = Counter()
    first_errors: Counter[str] = Counter()
    by_bucket: dict[str, list[bool]] = {}
    latencies: list[float] = []
    tokens_in: list[float] = []
    tokens_out: list[float] = []
    downgrades = 0
    analysed = 0
    for job in jobs.values():
        runs = job["analysis_runs"]
        if not runs:
            continue
        analysed += 1
        first = runs[0]
        first_status[first["status"]] += 1
        if first["status"] == "failed":
            first_errors[str(first["error_code"])] += 1
        parse = next((r for r in job["parse_runs"] if r["id"] == first["parse_run_id"]), None)
        size = len(parse["requirements"]) if parse else 0
        if first["error_code"] not in {"MATCHER_PROVIDER_RATE_LIMITED"}:
            by_bucket.setdefault(bucket(size), []).append(first["status"] == "succeeded")
        for run in runs:
            if run["status"] == "succeeded":
                downgrades += int(run["validation_failure_count"] or 0)
                if run["latency_ms"] is not None:
                    latencies.append(float(run["latency_ms"]))
                tokens_in.append(float(run["input_tokens"] or 0))
                tokens_out.append(float(run["output_tokens"] or 0))
    report: dict[str, Any] = {
        "pairs_analysed": analysed,
        "first_attempt_status": dict(first_status),
        "first_attempt_error_codes": dict(first_errors),
        "first_attempt_rate_limited": wilson(
            first_errors["MATCHER_PROVIDER_RATE_LIMITED"], analysed
        ),
        "success_by_requirement_count_excluding_rate_limits": {
            name: wilson(sum(values), len(values)) for name, values in sorted(by_bucket.items())
        },
        "validator_downgrades_total": downgrades,
        "latency_ms_successful": percentiles(latencies),
        "input_tokens_successful": percentiles(tokens_in),
        "output_tokens_successful": percentiles(tokens_out),
    }
    if labels_dir is not None and requirements_file is not None:
        report["against_labels"] = matcher_against_labels(
            dataset, jobs, labels_dir, requirements_file
        )
    return report


def latest_success(job: dict[str, Any]) -> dict[str, Any] | None:
    for run in reversed(job["analysis_runs"]):
        if run["status"] == "succeeded":
            return dict(run)
    return None


def matcher_against_labels(
    dataset: Path, jobs: dict[str, Any], labels_dir: Path, requirements_file: Path
) -> dict[str, Any]:
    resumes = load_resumes(dataset)
    pairs = {p["pair_id"]: p for p in json.loads(requirements_file.read_text(encoding="utf-8"))}
    labels = load_matcher_labels(labels_dir, resumes, pairs)
    confusion: Counter[str] = Counter()
    coverage_pairs: list[tuple[str, str]] = []
    cited_supported = cited_total = 0
    strata: dict[str, list[tuple[str, str]]] = {}
    for key, job in jobs.items():
        pair_id = key.removeprefix("job:")
        label = labels.get(pair_id)
        run = latest_success(job)
        if label is None or run is None:
            continue
        stratum = resumes[pairs[pair_id]["resume_id"]].stratum
        predicted = {m["requirement_id"]: m for m in run["matches"]}
        for entry in label.labels:
            match = predicted.get(entry.requirement_id)
            if match is None:
                continue
            confusion[f"{entry.verdict}->{match['verdict']}"] += 1
            pair = (COVERAGE[entry.verdict], COVERAGE[match["verdict"]])
            coverage_pairs.append(pair)
            strata.setdefault(stratum, []).append(pair)
            if match["verdict"] in {"matched", "partial"}:
                cited_total += 1
                cited_supported += match["exp_key"] in {e.exp_key for e in entry.evidence}
    n = len(coverage_pairs)
    support = Counter(expected for expected, _ in coverage_pairs)
    correct = Counter(expected for expected, got in coverage_pairs if expected == got)
    gap_n = support["gap"]
    return {
        "requirements_scored": n,
        "four_class_confusion_label_to_predicted": dict(sorted(confusion.items())),
        "coverage_exact": wilson(sum(e == g for e, g in coverage_pairs), n),
        "recall_by_coverage_class": {
            cls: wilson(correct[cls], support[cls]) for cls in ("full", "partial", "gap")
        },
        "overclaim_rate": wilson(sum(p in OVERCLAIM for p in coverage_pairs), n),
        "underclaim_rate": wilson(sum(p in UNDERCLAIM for p in coverage_pairs), n),
        "gap_to_positive_rate": wilson(
            sum(e == "gap" and g != "gap" for e, g in coverage_pairs), gap_n
        ),
        "positive_citations_pointing_at_labeled_evidence_experience": wilson(
            cited_supported, cited_total
        ),
        "by_resume_stratum": {
            name: {
                "requirements": len(values),
                "overclaim": wilson(sum(p in OVERCLAIM for p in values), len(values)),
                "underclaim": wilson(sum(p in UNDERCLAIM for p in values), len(values)),
            }
            for name, values in sorted(strata.items())
        },
    }


def score_cv_import(dataset: Path, state_path: Path) -> dict[str, Any]:
    resumes = load_resumes(dataset)
    state = State.load(state_path)
    report: dict[str, Any] = {}
    for suffix in ("md", "docx"):
        exact_titles = draft_count_match = total = skills = 0
        experiences_found = experiences_total = 0
        counts: list[float] = []
        for resume_id, resume in resumes.items():
            record = state.get(f"cv_import:{resume_id}.{suffix}")
            if record is None:
                continue
            total += 1
            titles = record["draft_titles"]
            counts.append(float(record["draft_count"]))
            expected_titles = [exp.title for exp in resume.experiences]
            found = sum(title in titles for title in expected_titles)
            experiences_found += found
            experiences_total += len(expected_titles)
            exact_titles += found == len(expected_titles)
            # Rendered CVs carry 2 non-experience blocks (header, education).
            draft_count_match += record["draft_count"] == len(expected_titles) + 2
            skills += sum(record["draft_skill_counts"])
        report[suffix] = {
            "imports": total,
            "drafts_per_cv": percentiles(counts),
            "cvs_where_every_experience_became_its_own_draft": wilson(exact_titles, total),
            "experiences_recovered_as_separate_drafts": wilson(
                experiences_found, experiences_total
            ),
            "cvs_with_expected_draft_count": wilson(draft_count_match, total),
            "skills_extracted_total": skills,
        }
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--results", type=Path)
    parser.add_argument("--parser-labels", type=Path)
    parser.add_argument("--matcher-labels", type=Path)
    parser.add_argument("--requirements", type=Path)
    parser.add_argument("--cv-import-state", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report: dict[str, Any] = {"dataset": str(args.dataset)}
    if args.results:
        results = json.loads(args.results.read_text(encoding="utf-8"))
        report["parser"] = score_parser(args.dataset, results, args.parser_labels)
        report["matcher"] = score_matcher(
            args.dataset, results, args.matcher_labels, args.requirements
        )
    if args.cv_import_state:
        report["cv_import"] = score_cv_import(args.dataset, args.cv_import_state)
    args.out.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=1)[:6000])


if __name__ == "__main__":
    main()
