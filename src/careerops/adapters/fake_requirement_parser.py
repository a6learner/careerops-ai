import re

from careerops.domain.parse_runs import (
    FAKE_PARSE_MODEL_NAME,
    ParsedRequirement,
    ParserOutput,
    RequirementCategory,
)


class FakeRequirementParser:
    async def parse(self, input_text: str) -> ParserOutput:
        return ParserOutput(
            model_name=FAKE_PARSE_MODEL_NAME,
            requirements=parse_requirements_deterministically(input_text),
        )


def parse_requirements_deterministically(input_text: str) -> tuple[ParsedRequirement, ...]:
    requirements: list[ParsedRequirement] = []
    for match in re.finditer(r"[^.\n;•-][^.\n;]*", input_text):
        text = " ".join(match.group(0).split())
        if len(text) < 4:
            continue
        requirements.append(
            ParsedRequirement(
                category=classify_requirement(text),
                text=text,
                skill_normalized=extract_skill(text),
                source_span_start=match.start(),
                source_span_end=match.end(),
            )
        )
    if requirements:
        return tuple(requirements)
    stripped = input_text.strip()
    if stripped == "":
        return ()
    start = input_text.index(stripped)
    return (
        ParsedRequirement(
            category=RequirementCategory.RESPONSIBILITY,
            text=stripped,
            skill_normalized=extract_skill(stripped),
            source_span_start=start,
            source_span_end=start + len(stripped),
        ),
    )


def classify_requirement(text: str) -> RequirementCategory:
    lowered = text.lower()
    if any(word in lowered for word in ("degree", "student", "bachelor", "master")):
        return RequirementCategory.EDUCATION
    if any(word in lowered for word in ("nice to have", "preferred", "plus", "bonus")):
        return RequirementCategory.NICE_TO_HAVE
    if any(word in lowered for word in ("required", "must", "experience", "proficient")):
        return RequirementCategory.MUST_HAVE
    return RequirementCategory.RESPONSIBILITY


def extract_skill(text: str) -> str | None:
    lowered = text.lower()
    known_skills = (
        "python",
        "fastapi",
        "postgresql",
        "redis",
        "sql",
        "docker",
        "kubernetes",
        "aws",
        "java",
        "typescript",
        "react",
    )
    for skill in known_skills:
        if skill in lowered:
            return skill
    return None
