import json
from hashlib import sha256
from uuid import UUID

import httpx
import pytest
from tests.test_evidence_retrieval import make_experience, make_requirement

from careerops.adapters.groq_evidence_matcher import GroqEvidenceMatcher
from careerops.domain.errors import (
    EvidenceMatcherError,
    EvidenceMatcherFailureReason,
    MatcherOutputFailureReason,
    MatcherOutputValidationError,
)
from careerops.domain.evidence_matching import (
    MATCHER_PROMPT_VERSION,
    MATCHER_SCHEMA_VERSION,
    EvidenceMatcherInput,
    EvidenceVerdict,
)
from careerops.domain.evidence_retrieval import retrieve_evidence_candidates
from careerops.services.evidence_matcher_contract import build_evidence_matcher_input


async def no_sleep(_: float) -> None:
    return None


def make_matcher(
    transport: httpx.MockTransport,
    *,
    max_attempts: int = 1,
) -> GroqEvidenceMatcher:
    return GroqEvidenceMatcher(
        api_key="test-key",
        model="openai/gpt-oss-20b",
        base_url="https://api.groq.test/openai/v1/",
        timeout_seconds=1.0,
        max_attempts=max_attempts,
        retry_base_delay_seconds=0.0,
        max_output_tokens=500,
        transport=transport,
        sleep=no_sleep,
    )


def matcher_input() -> tuple[UUID, UUID, int, EvidenceMatcherInput]:
    requirement = make_requirement(skill="Python", text="Python required")
    experience = make_experience(
        "00000000-0000-0000-0000-000000000001",
        skills=("Python",),
        description="Built APIs.",
    )
    typed_input = build_evidence_matcher_input(
        retrieve_evidence_candidates((requirement,), (experience,))
    )
    return requirement.id, experience.id, experience.version, typed_input


def successful_response(request: httpx.Request, content: str) -> httpx.Response:
    return httpx.Response(
        200,
        request=request,
        json={
            "model": "openai/gpt-oss-20b",
            "choices": [{"message": {"content": content}}],
            "usage": {"prompt_tokens": 120, "completion_tokens": 30},
        },
    )


@pytest.mark.asyncio
async def test_groq_matcher_uses_minimal_input_and_strict_independent_schema() -> None:
    requirement_id, experience_id, experience_version, typed_input = matcher_input()

    def handle(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert request.url == "https://api.groq.test/openai/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer test-key"
        assert body["response_format"]["json_schema"]["strict"] is True
        assert "not explicitly mentioned" in body["messages"][0]["content"]
        assert supplied_prompt_version(body) == MATCHER_PROMPT_VERSION
        schema_text = json.dumps(body["response_format"]["json_schema"]["schema"])
        assert "oneOf" not in schema_text
        assert "discriminator" not in schema_text
        assert "anyOf" in schema_text
        matches_schema = body["response_format"]["json_schema"]["schema"][
            "properties"
        ]["matches"]
        positive_schema, gap_schema = matches_schema["items"]["anyOf"]
        assert positive_schema["properties"]["verdict"]["enum"] == [
            "matched",
            "partial",
        ]
        assert positive_schema["properties"]["evidence"]["type"] == "object"
        assert gap_schema["properties"]["evidence"] == {"type": "null"}
        assert positive_schema["properties"]["confidence"]["minimum"] == 0.0
        assert positive_schema["properties"]["confidence"]["maximum"] == 1.0
        supplied = json.loads(body["messages"][1]["content"])
        serialized = json.dumps(supplied)
        assert "user_id" not in serialized
        assert "score" not in serialized
        assert supplied["requirements"][0]["text"] == "Python required"
        return successful_response(
            request,
            json.dumps(
                {
                    "schema_version": MATCHER_SCHEMA_VERSION,
                    "matches": [
                        {
                            "requirement_id": str(requirement_id),
                            "verdict": "matched",
                            "evidence": {
                                "experience_id": str(experience_id),
                                "experience_version": experience_version,
                                "source_ref": "skill:0",
                                "quote": "Python",
                            },
                            "confidence": 0.9,
                        }
                    ],
                }
            ),
        )

    matcher = make_matcher(httpx.MockTransport(handle))
    output = await matcher.match(typed_input)

    assert output.model_name == "openai/gpt-oss-20b"
    assert output.input_tokens == 120
    assert output.output_tokens == 30
    assert output.matches[0].verdict is EvidenceVerdict.MATCHED
    assert output.matches[0].quote == "Python"
    assert matcher.request_attempt_count == 1


def supplied_prompt_version(body: dict[str, object]) -> str:
    messages = body["messages"]
    assert isinstance(messages, list)
    user_message = messages[1]
    assert isinstance(user_message, dict)
    supplied = json.loads(str(user_message["content"]))
    return str(supplied["prompt_version"])


@pytest.mark.asyncio
async def test_groq_matcher_normalizes_null_evidence_for_gap() -> None:
    requirement_id, _, _, typed_input = matcher_input()

    def handle(request: httpx.Request) -> httpx.Response:
        return successful_response(
            request,
            json.dumps(
                {
                    "schema_version": MATCHER_SCHEMA_VERSION,
                    "matches": [
                        {
                            "requirement_id": str(requirement_id),
                            "verdict": "missing",
                            "evidence": None,
                            "confidence": 0.8,
                        }
                    ],
                }
            ),
        )

    output = await make_matcher(httpx.MockTransport(handle)).match(typed_input)

    assert output.matches[0].verdict is EvidenceVerdict.MISSING
    assert output.matches[0].experience_id is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("content", "reason"),
    [
        ("not-json", MatcherOutputFailureReason.INVALID_JSON),
        (
            '{"schema_version":"evidence-matcher-schema-v1","matches":[],"extra":true}',
            MatcherOutputFailureReason.INVALID_SCHEMA,
        ),
    ],
)
async def test_groq_matcher_classifies_invalid_model_output(
    content: str,
    reason: MatcherOutputFailureReason,
) -> None:
    _, _, _, typed_input = matcher_input()

    def handle(request: httpx.Request) -> httpx.Response:
        return successful_response(request, content)

    with pytest.raises(MatcherOutputValidationError) as captured:
        await make_matcher(httpx.MockTransport(handle)).match(typed_input)

    assert captured.value.reason is reason
    assert captured.value.diagnostic is not None
    assert content not in captured.value.diagnostic
    assert captured.value.response_sha256 == sha256(content.encode("utf-8")).hexdigest()
    assert captured.value.response_size_bytes == len(content.encode("utf-8"))
    assert captured.value.input_tokens == 120
    assert captured.value.output_tokens == 30


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status_code", "reason"),
    [
        (401, EvidenceMatcherFailureReason.MISCONFIGURED),
        (429, EvidenceMatcherFailureReason.RATE_LIMITED),
        (503, EvidenceMatcherFailureReason.UNAVAILABLE),
        (400, EvidenceMatcherFailureReason.REQUEST_FAILED),
    ],
)
async def test_groq_matcher_classifies_http_failure(
    status_code: int,
    reason: EvidenceMatcherFailureReason,
) -> None:
    _, _, _, typed_input = matcher_input()

    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, request=request)

    with pytest.raises(EvidenceMatcherError) as captured:
        await make_matcher(httpx.MockTransport(handle)).match(typed_input)

    assert captured.value.reason is reason


@pytest.mark.asyncio
async def test_groq_matcher_classifies_timeout() -> None:
    _, _, _, typed_input = matcher_input()

    def handle(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    with pytest.raises(EvidenceMatcherError) as captured:
        await make_matcher(httpx.MockTransport(handle)).match(typed_input)

    assert captured.value.reason is EvidenceMatcherFailureReason.TIMEOUT


@pytest.mark.asyncio
async def test_groq_matcher_paces_consecutive_requests() -> None:
    requirement_id, _, _, typed_input = matcher_input()
    delays: list[float] = []
    clock_values = iter((0.0, 5.0, 11.0))

    async def record_sleep(delay: float) -> None:
        delays.append(delay)

    def handle(request: httpx.Request) -> httpx.Response:
        return successful_response(
            request,
            json.dumps(
                {
                    "schema_version": MATCHER_SCHEMA_VERSION,
                    "matches": [
                        {
                            "requirement_id": str(requirement_id),
                            "verdict": "missing",
                            "evidence": None,
                            "confidence": 0.8,
                        }
                    ],
                }
            ),
        )

    matcher = GroqEvidenceMatcher(
        api_key="test-key",
        model="openai/gpt-oss-20b",
        base_url="https://api.groq.test/openai/v1",
        timeout_seconds=1.0,
        max_attempts=1,
        retry_base_delay_seconds=0.0,
        max_output_tokens=500,
        minimum_request_interval_seconds=11.0,
        transport=httpx.MockTransport(handle),
        sleep=record_sleep,
        clock=lambda: next(clock_values),
    )

    await matcher.match(typed_input)
    await matcher.match(typed_input)

    assert delays == [6.0]
