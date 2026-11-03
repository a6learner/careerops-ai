"""Merge collector outputs into the frozen large_scale_v1 development dataset.

Usage:
    python -m scripts.large_eval.build_dataset --scratch <dir> --out evals/large_scale_v1
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import unicodedata
from collections import Counter, defaultdict
from collections.abc import Iterable
from pathlib import Path

from pydantic import ValidationError

from scripts.large_eval.models import (
    Collector,
    JdRecord,
    RawJd,
    ResumeRecord,
    RoleFamily,
    Stratum,
)

COLLECTORS: tuple[tuple[Collector, str], ...] = (
    ("notion", "jd/notion/jds.jsonl"),
    ("greenhouse_agent", "jd/greenhouse/jds.jsonl"),
    ("codex", "jd/codex/jds.jsonl"),
)
RESUME_FILES = ("resumes/agent/resumes.json", "resumes/codex/resumes.json")
MAX_PER_COMPANY = 4
NEAR_DUPLICATE_JACCARD = 0.85
PAIRS_PER_RESUME = 3
SEED = 20261101

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE = re.compile(r"(?<!\w)(?:\+?\d[\d ()./-]{8,}\d)(?!\w)")
_WS = re.compile(r"[ \t ]+")

FIT: dict[Stratum, tuple[tuple[RoleFamily, ...], tuple[RoleFamily, ...]]] = {
    "backend": (("backend", "infra"), ("general_swe", "data")),
    "ai_ml": (("ai_ml",), ("data", "general_swe")),
    "fullstack_frontend": (("frontend", "general_swe"), ("backend", "mobile")),
    "systems_infra": (("infra", "security"), ("backend", "general_swe")),
    "data": (("data",), ("ai_ml", "backend")),
    "mobile_other": (("mobile", "frontend", "other"), ("general_swe", "security")),
    "sparse_novice": (("general_swe",), ("backend", "frontend")),
    "adversarial": (("backend", "ai_ml", "general_swe"), ("infra", "data")),
}


def redact_phone(match: re.Match[str]) -> str:
    digits = sum(char.isdigit() for char in match.group())
    return "[redacted]" if digits >= 9 else match.group()


def clean_description(text: str) -> str:
    text = unicodedata.normalize("NFC", text).replace("\r\n", "\n").replace("\r", "\n")
    text = _EMAIL.sub("[redacted]", text)
    text = _PHONE.sub(redact_phone, text)
    lines = [_WS.sub(" ", line).strip() for line in text.split("\n")]
    out: list[str] = []
    for line in lines:
        if line or (out and out[-1]):
            out.append(line)
    return "\n".join(out).strip()


def shingles(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", text.casefold())
    return {" ".join(words[i : i + 5]) for i in range(max(len(words) - 4, 1))}


def jaccard(left: set[str], right: set[str]) -> float:
    return len(left & right) / max(len(left | right), 1)


def is_near_duplicate(candidate: set[str], kept: list[set[str]]) -> bool:
    return any(jaccard(candidate, other) >= NEAR_DUPLICATE_JACCARD for other in kept)


def load_jsonl(path: Path) -> Iterable[dict[str, object]]:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            yield json.loads(line)


def collect_jds(scratch: Path) -> tuple[list[JdRecord], Counter[str]]:
    rejected: Counter[str] = Counter()
    kept: list[JdRecord] = []
    kept_shingles: list[set[str]] = []
    per_company: Counter[str] = Counter()
    seen_urls: set[str] = set()
    for collector, relative in COLLECTORS:
        for raw in load_jsonl(scratch / relative):
            if isinstance(raw.get("raw_description"), str):
                raw["raw_description"] = clean_description(str(raw["raw_description"]))
            try:
                jd = RawJd.model_validate(raw)
            except ValidationError:
                rejected[f"{collector}:invalid"] += 1
                continue
            url_key = jd.source_url.split("?")[0].rstrip("/").casefold()
            company_key = jd.company.casefold().strip()
            if url_key in seen_urls:
                rejected[f"{collector}:duplicate_url"] += 1
                continue
            if per_company[company_key] >= MAX_PER_COMPANY:
                rejected[f"{collector}:company_cap"] += 1
                continue
            text_shingles = shingles(jd.raw_description)
            if any(
                jaccard(text_shingles, other) >= NEAR_DUPLICATE_JACCARD for other in kept_shingles
            ):
                rejected[f"{collector}:near_duplicate"] += 1
                continue
            digest = hashlib.sha256(jd.raw_description.encode("utf-8")).hexdigest()
            kept.append(
                JdRecord(
                    jd_id=f"jd-{digest[:10]}",
                    collector=collector,
                    sha256=digest,
                    **jd.model_dump(),
                )
            )
            kept_shingles.append(text_shingles)
            per_company[company_key] += 1
            seen_urls.add(url_key)
    return kept, rejected


def collect_resumes(scratch: Path) -> list[ResumeRecord]:
    resumes: list[ResumeRecord] = []
    for relative in RESUME_FILES:
        payload = json.loads((scratch / relative).read_text(encoding="utf-8"))
        resumes.extend(ResumeRecord.model_validate(item) for item in payload)
    ids = [resume.resume_id for resume in resumes]
    keys = [exp.exp_key for resume in resumes for exp in resume.experiences]
    if len(set(ids)) != len(ids) or len(set(keys)) != len(keys):
        raise ValueError("resume_id and exp_key values must be unique")
    for resume in resumes:
        blob = json.dumps(resume.model_dump())
        if _EMAIL.search(blob):
            raise ValueError(f"{resume.resume_id} contains an email-like string")
    return sorted(resumes, key=lambda resume: resume.resume_id)


def assign_pairs(
    resumes: list[ResumeRecord], jds: list[JdRecord]
) -> tuple[list[dict[str, str]], list[str]]:
    """Give each resume one high, one medium and one low designed-fit JD; JD used once."""
    rng = random.Random(SEED)
    pool: dict[RoleFamily, list[JdRecord]] = defaultdict(list)
    for jd in sorted(jds, key=lambda record: record.jd_id):
        pool[jd.role_family].append(jd)
    for records in pool.values():
        rng.shuffle(records)
    used: set[str] = set()

    def take(families: Iterable[RoleFamily], avoid: set[RoleFamily]) -> JdRecord:
        ordered = list(families) or [f for f in pool if f not in avoid]
        for family in ordered:
            for jd in pool[family]:
                if jd.jd_id not in used:
                    used.add(jd.jd_id)
                    return jd
        for family in sorted(pool, key=lambda f: -len(pool[f])):
            if family in avoid:
                continue
            for jd in pool[family]:
                if jd.jd_id not in used:
                    used.add(jd.jd_id)
                    return jd
        raise ValueError("not enough JDs to pair")

    pairs: list[dict[str, str]] = []
    order = list(resumes)
    rng.shuffle(order)
    for resume in order:
        high, medium = FIT[resume.stratum]
        related = set(high) | set(medium)
        chosen = (
            ("high", take(high, set())),
            ("medium", take(medium, set(high))),
            ("low", take((), related)),
        )
        for fit, jd in chosen:
            pairs.append(
                {
                    "pair_id": f"{resume.resume_id}-{jd.jd_id}",
                    "resume_id": resume.resume_id,
                    "jd_id": jd.jd_id,
                    "designed_fit": fit,
                }
            )
    leftover = sorted(jd.jd_id for jd in jds if jd.jd_id not in used)
    pairs.sort(key=lambda pair: pair["pair_id"])
    return pairs, leftover


def render_markdown(resume: ResumeRecord) -> str:
    """Resume text with blank lines between entries (best case for the CV splitter)."""
    edu = resume.education
    blocks = [
        f"{resume.name}\nSoftware engineering candidate",
        "Education\n"
        + f"{edu.school}, {edu.degree}, expected {edu.grad}"
        + (f", GPA {edu.gpa}" if edu.gpa else "")
        + (f"\nRelevant coursework: {', '.join(edu.coursework)}" if edu.coursework else ""),
    ]
    for exp in resume.experiences:
        lines = [exp.title, exp.description, f"Skills: {', '.join(exp.skills)}"]
        if exp.outcome:
            lines.append(f"Outcome: {exp.outcome}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks) + "\n"


def render_docx(resume: ResumeRecord, path: Path) -> None:
    """Typical word-processor layout: one paragraph per line, no empty paragraphs."""
    from docx import Document

    document = Document()
    document.add_heading(resume.name, level=1)
    document.add_paragraph("Education")
    edu = resume.education
    document.add_paragraph(f"{edu.school}, {edu.degree}, expected {edu.grad}")
    document.add_paragraph("Experience")
    for exp in resume.experiences:
        document.add_paragraph(exp.title)
        document.add_paragraph(exp.description)
        document.add_paragraph(f"Skills: {', '.join(exp.skills)}")
        if exp.outcome:
            document.add_paragraph(f"Outcome: {exp.outcome}")
    document.save(str(path))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scratch", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True)
    (out / "cv_files").mkdir(exist_ok=True)

    jds, rejected = collect_jds(args.scratch)
    resumes = collect_resumes(args.scratch)
    pairs, parser_only = assign_pairs(resumes, jds)

    write_json(out / "jds.json", [jd.model_dump() for jd in jds])
    write_json(out / "resumes.json", [resume.model_dump() for resume in resumes])
    write_json(out / "pairs.json", {"pairs": pairs, "parser_only_jd_ids": parser_only})
    for resume in resumes:
        (out / "cv_files" / f"{resume.resume_id}.md").write_text(
            render_markdown(resume), encoding="utf-8"
        )
        render_docx(resume, out / "cv_files" / f"{resume.resume_id}.docx")

    files = sorted(p for p in out.rglob("*") if p.is_file() and p.name != "manifest.json")
    manifest = {
        "name": "large_scale_v1",
        "split": "development",
        "labels": "model-labeled (Claude subagents + Codex, adjudicated); not author-labeled",
        "jd_count": len(jds),
        "resume_count": len(resumes),
        "pair_count": len(pairs),
        "parser_only_jd_count": len(parser_only),
        "jd_by_collector": dict(Counter(jd.collector for jd in jds)),
        "jd_by_seniority": dict(Counter(jd.seniority for jd in jds)),
        "jd_by_role_family": dict(Counter(jd.role_family for jd in jds)),
        "resume_by_stratum": dict(Counter(resume.stratum for resume in resumes)),
        "rejected_during_merge": dict(rejected),
        "files": {str(p.relative_to(out)).replace("\\", "/"): sha256_file(p) for p in files},
    }
    write_json(out / "manifest.json", manifest)
    print(json.dumps({k: v for k, v in manifest.items() if k != "files"}, indent=2))


if __name__ == "__main__":
    main()
