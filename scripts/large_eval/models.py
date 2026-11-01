"""Typed records for the large_scale_v1 development evaluation."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SourceType = Literal["greenhouse_api", "lever_api", "ashby_api", "html_page"]
RoleFamily = Literal[
    "general_swe", "backend", "ai_ml", "infra", "data", "frontend", "mobile", "security", "other"
]
Seniority = Literal["intern", "new_grad", "mid"]
Collector = Literal["notion", "greenhouse_agent", "codex"]
ExperienceKind = Literal["project", "work", "research", "course", "other"]
Stratum = Literal[
    "backend",
    "ai_ml",
    "fullstack_frontend",
    "systems_infra",
    "data",
    "mobile_other",
    "sparse_novice",
    "adversarial",
]
Category = Literal["must_have", "nice_to_have", "responsibility", "education"]
Verdict = Literal["matched", "partial", "insufficient_evidence", "missing"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RawJd(BaseModel):
    """One collector record; extra collector fields are ignored."""

    model_config = ConfigDict(extra="ignore")

    source_type: SourceType
    company: str = Field(min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=200)
    source_url: str = Field(min_length=8, max_length=2048)
    location: str | None = None
    fetched_at: str
    role_family: RoleFamily
    seniority: Seniority
    raw_description: str = Field(min_length=400, max_length=50_000)


class JdRecord(_Strict):
    jd_id: str
    collector: Collector
    source_type: SourceType
    company: str
    title: str
    source_url: str
    location: str | None
    fetched_at: str
    role_family: RoleFamily
    seniority: Seniority
    raw_description: str
    sha256: str


class ResumeExperience(_Strict):
    exp_key: str
    title: str = Field(min_length=1, max_length=200)
    kind: ExperienceKind
    description: str = Field(min_length=20, max_length=10_000)
    skills: tuple[str, ...] = Field(min_length=1, max_length=50)
    outcome: str | None = Field(default=None, max_length=2_000)


class Education(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    school: str
    degree: str
    grad: str
    gpa: str | None = None
    coursework: tuple[str, ...] = ()


class ResumeRecord(_Strict):
    resume_id: str
    stratum: Stratum
    persona_summary: str
    name: str
    education: Education
    experiences: tuple[ResumeExperience, ...] = Field(min_length=4, max_length=8)
    traps: tuple[str, ...] = ()


class ParserLabel(_Strict):
    candidate_id: int
    text: str
    category: Category
    skill_normalized: str | None


class ParserLabelSet(_Strict):
    jd_id: str
    labeler: str
    requirements: tuple[ParserLabel, ...]


class EvidenceLabel(_Strict):
    exp_key: str
    source_ref: str
    quote: str


class MatcherLabel(_Strict):
    requirement_id: str
    verdict: Verdict
    evidence: tuple[EvidenceLabel, ...] = ()
    gap_reason_code: str | None = None
    rationale: str = ""


class MatcherLabelSet(_Strict):
    pair_id: str
    labeler: str
    labels: tuple[MatcherLabel, ...]
