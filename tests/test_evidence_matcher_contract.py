import json
from dataclasses import asdict, replace
from uuid import UUID

import pytest
from pydantic import ValidationError
from tests.test_evidence_retrieval import make_experience, make_requirement

from careerops.adapters.evidence_matcher_schema import (
    evidence_matcher_instructions,
    matcher_response_json_schema,
    parse_matcher_response,
)
from careerops.domain.errors import MatcherOutputFailureReason, MatcherOutputValidationError
from careerops.domain.evidence_matching import (
    MATCHER_PROMPT_VERSION,
    MATCHER_PROMPT_VERSION_V1,
    MATCHER_PROMPT_VERSION_V2,
    MATCHER_PROMPT_VERSION_V3,
    MATCHER_PROMPT_VERSION_V4,
    MATCHER_PROMPT_VERSION_V5,
    MATCHER_SCHEMA_VERSION,
    EvidenceVerdict,
)
from careerops.domain.evidence_retrieval import retrieve_evidence_candidates
from careerops.services.evidence_matcher_contract import build_evidence_matcher_input


def test_matcher_input_is_minimal_typed_and_deduplicates_experiences() -> None:
    python = make_requirement(skill="Python", text="Python required")
    api = replace(
        make_requirement(skill=None, text="APIs required"),
        id=UUID("10000000-0000-0000-0000-000000000002"),
    )
    experience = make_experience(
        "00000000-0000-0000-0000-000000000001",
        skills=("Python",),
        description="Built APIs.",
    )

    matcher_input = build_evidence_matcher_input(
        retrieve_evidence_candidates((python, api), (experience,))
    )

    assert matcher_input.schema_version == MATCHER_SCHEMA_VERSION
    assert matcher_input.prompt_version == MATCHER_PROMPT_VERSION
    assert len(matcher_input.experiences) == 1
    assert [candidate.rank for candidate in matcher_input.candidate_sets[0].candidates] == [1]
    payload = asdict(matcher_input)
    serialized = json.dumps(payload, default=str)
    assert "user_id" not in serialized
    assert "score" not in serialized
    assert "content_hash" not in serialized
    assert {source.source_ref for source in matcher_input.experiences[0].sources} >= {
        "title",
        "description",
        "skill:0",
    }


def test_response_schema_parses_positive_and_gap_verdicts() -> None:
    requirement = make_requirement(skill="Python", text="Python required")
    experience = make_experience(
        "00000000-0000-0000-0000-000000000001",
        skills=("Python",),
        description="Built APIs.",
    )
    gap_requirement = make_requirement(skill="Kubernetes", text="Kubernetes required")
    content = json.dumps(
        {
            "schema_version": MATCHER_SCHEMA_VERSION,
            "matches": [
                {
                    "requirement_id": str(requirement.id),
                    "verdict": "matched",
                    "evidence": {
                        "experience_id": str(experience.id),
                        "experience_version": experience.version,
                        "source_ref": "skill:0",
                        "quote": "Python",
                    },
                    "confidence": 0.9,
                },
                {
                    "requirement_id": str(gap_requirement.id),
                    "verdict": "missing",
                    "confidence": 0.8,
                },
            ],
        }
    )

    output = parse_matcher_response(
        content,
        model_name="test-real-matcher",
        input_tokens=10,
        output_tokens=5,
    )

    assert output.model_name == "test-real-matcher"
    assert output.input_tokens == 10
    assert output.matches[0].verdict is EvidenceVerdict.MATCHED
    assert output.matches[0].source_ref == "skill:0"
    assert output.matches[1].verdict is EvidenceVerdict.MISSING
    assert output.matches[1].experience_id is None


def test_response_parser_distinguishes_invalid_json() -> None:
    with pytest.raises(MatcherOutputValidationError) as exc_info:
        parse_matcher_response("not-json", model_name="test-real-matcher")

    assert exc_info.value.reason is MatcherOutputFailureReason.INVALID_JSON


@pytest.mark.parametrize(
    "match",
    [
        {
            "requirement_id": "00000000-0000-0000-0000-000000000001",
            "verdict": "missing",
            "confidence": 0.8,
            "unexpected": True,
        },
        {
            "requirement_id": "00000000-0000-0000-0000-000000000001",
            "verdict": "matched",
            "confidence": 0.8,
        },
        {
            "requirement_id": "00000000-0000-0000-0000-000000000001",
            "verdict": "missing",
            "evidence": {
                "experience_id": "00000000-0000-0000-0000-000000000002",
                "experience_version": 1,
                "source_ref": "description",
                "quote": "claim",
            },
            "confidence": 0.8,
        },
        {
            "requirement_id": "00000000-0000-0000-0000-000000000001",
            "verdict": "missing",
            "confidence": 1.1,
        },
    ],
)
def test_response_schema_rejects_extra_or_inconsistent_fields(match: dict[str, object]) -> None:
    content = json.dumps(
        {
            "schema_version": MATCHER_SCHEMA_VERSION,
            "matches": [match],
        }
    )

    with pytest.raises(MatcherOutputValidationError) as exc_info:
        parse_matcher_response(content, model_name="test-real-matcher")

    assert exc_info.value.reason is MatcherOutputFailureReason.INVALID_SCHEMA


def test_schema_and_prompt_are_strict_and_treat_inputs_as_untrusted() -> None:
    schema = matcher_response_json_schema()
    assert schema["additionalProperties"] is False
    instructions = evidence_matcher_instructions(MATCHER_PROMPT_VERSION)
    assert "untrusted data" in instructions
    assert "exactly once" in instructions
    assert "exact verbatim substring" in instructions
    assert "not explicitly mentioned" in instructions
    assert "independently testable necessary conditions" in instructions
    assert "never combine different experiences" in instructions
    assert "grounded but incomplete quote cannot justify matched" in instructions
    assert "specific measured or causal result" in instructions
    assert "Gap verdicts must return null evidence" in instructions
    assert "finite number from 0 through 1" in instructions


def test_prompt_v2_remains_available_for_durable_work_bound_to_v2() -> None:
    instructions = evidence_matcher_instructions(MATCHER_PROMPT_VERSION_V2)

    assert "Do not use partial for an unverified metric" in instructions
    assert "independently testable necessary conditions" not in instructions


def test_prompt_v3_remains_available_for_durable_work_bound_to_v3() -> None:
    instructions = evidence_matcher_instructions(MATCHER_PROMPT_VERSION_V3)

    assert "independently testable necessary conditions" in instructions
    assert "If any candidate proves at least one such condition" not in instructions


def test_prompt_v4_remains_available_for_durable_work_bound_to_v4() -> None:
    instructions = evidence_matcher_instructions(MATCHER_PROMPT_VERSION_V4)

    assert "If any candidate proves at least one such condition" in instructions
    assert "Then classify in this order" not in instructions


def test_prompt_v5_remains_available_for_saved_evaluation_evidence() -> None:
    instructions = evidence_matcher_instructions(MATCHER_PROMPT_VERSION_V5)

    assert "Then classify in this order" in instructions


def test_prompt_v1_remains_available_for_durable_work_bound_to_v1() -> None:
    instructions = evidence_matcher_instructions(MATCHER_PROMPT_VERSION_V1)

    assert "no candidate is relevant" in instructions
    assert "not explicitly mentioned" not in instructions


def test_matcher_input_rejects_unknown_prompt_version() -> None:
    with pytest.raises(MatcherOutputValidationError) as exc_info:
        build_evidence_matcher_input((), prompt_version="unknown-prompt")

    assert exc_info.value.reason is MatcherOutputFailureReason.INVALID_CONTRACT


def test_schema_version_is_fixed() -> None:
    with pytest.raises(ValidationError):
        # The public schema class stays strict even before an HTTP adapter exists.
        from careerops.adapters.evidence_matcher_schema import MatcherResponsePayload

        MatcherResponsePayload.model_validate(
            {"schema_version": "future-version", "matches": []}
        )
