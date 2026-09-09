import json

import httpx
import pytest

from careerops.adapters.groq_requirement_parser import (
    GroqRequirementParser,
    extract_source_candidates,
)
from careerops.domain.errors import ParserOutputValidationError, RequirementParserError
from careerops.domain.parse_runs import RequirementCategory


def make_parser(
    handler: httpx.MockTransport,
    *,
    max_attempts: int = 2,
) -> GroqRequirementParser:
    return GroqRequirementParser(
        api_key="test-key",
        model="openai/gpt-oss-20b",
        base_url="https://api.groq.test/openai/v1/",
        timeout_seconds=1.0,
        max_attempts=max_attempts,
        retry_base_delay_seconds=0.0,
        max_output_tokens=500,
        transport=handler,
    )


def successful_response(request: httpx.Request, content: str) -> httpx.Response:
    return httpx.Response(
        200,
        request=request,
        json={
            "model": "openai/gpt-oss-20b",
            "choices": [{"message": {"content": content}}],
            "usage": {"prompt_tokens": 42, "completion_tokens": 17},
        },
    )


def test_source_candidates_preserve_bullets_and_unicode_spans() -> None:
    input_text = "Responsibilities:\n- Build APIs.\n你需要熟悉 Python。"

    candidates = extract_source_candidates(input_text)

    assert [item.text for item in candidates] == [
        "Responsibilities:",
        "Build APIs.",
        "你需要熟悉 Python。",
    ]
    for candidate in candidates:
        assert input_text[candidate.source_span_start : candidate.source_span_end] == candidate.text


@pytest.mark.asyncio
async def test_groq_parser_requests_strict_schema_and_builds_grounded_spans() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert request.url == "https://api.groq.test/openai/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer test-key"
        assert body["response_format"]["json_schema"]["strict"] is True
        assert "source_span_start" not in json.dumps(body["response_format"])
        supplied = json.loads(body["messages"][1]["content"])["candidates"]
        assert [item["text"] for item in supplied] == [
            "Python experience required.",
            "Preferred Redis.",
        ]
        return successful_response(
            request,
            json.dumps(
                {
                    "requirements": [
                        {
                            "category": "must_have",
                            "candidate_id": 0,
                            "skill_normalized": " Python ",
                        },
                        {
                            "category": "nice_to_have",
                            "candidate_id": 1,
                            "skill_normalized": "redis",
                        },
                    ]
                }
            ),
        )

    output = await make_parser(httpx.MockTransport(handle)).parse(
        "Python experience required. Preferred Redis."
    )

    assert output.model_name == "openai/gpt-oss-20b"
    assert output.input_tokens == 42
    assert output.output_tokens == 17
    assert output.requirements[0].category == RequirementCategory.MUST_HAVE
    assert output.requirements[0].skill_normalized == "python"
    assert output.requirements[0].source_span_start == 0
    assert output.requirements[0].source_span_end == 27
    assert output.requirements[1].source_span_start == 28


@pytest.mark.asyncio
async def test_groq_parser_retries_transient_failure_once() -> None:
    calls = 0

    def handle(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(503, request=request)
        return successful_response(
            request,
            '{"requirements":[{"category":"must_have","candidate_id":0,'
            '"skill_normalized":"python"}]}',
        )

    output = await make_parser(httpx.MockTransport(handle)).parse("Python required.")

    assert calls == 2
    assert len(output.requirements) == 1


@pytest.mark.asyncio
async def test_groq_parser_retries_transport_failure_once() -> None:
    calls = 0

    def handle(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise httpx.ConnectError("connection failed", request=request)
        return successful_response(
            request,
            '{"requirements":[{"category":"must_have","candidate_id":0,'
            '"skill_normalized":"python"}]}',
        )

    output = await make_parser(httpx.MockTransport(handle)).parse("Python required.")

    assert calls == 2
    assert len(output.requirements) == 1


@pytest.mark.asyncio
async def test_groq_parser_does_not_retry_permanent_http_failure() -> None:
    calls = 0

    def handle(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(401, request=request)

    with pytest.raises(RequirementParserError):
        await make_parser(httpx.MockTransport(handle)).parse("Python required.")

    assert calls == 1


@pytest.mark.asyncio
async def test_groq_parser_rejects_unknown_candidate_id() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return successful_response(
            request,
            '{"requirements":[{"category":"must_have","candidate_id":99,'
            '"skill_normalized":"java"}]}',
        )

    with pytest.raises(ParserOutputValidationError):
        await make_parser(httpx.MockTransport(handle)).parse("Python required.")


@pytest.mark.asyncio
async def test_groq_parser_uses_distinct_spans_for_repeated_text() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return successful_response(
            request,
            '{"requirements":['
            '{"category":"must_have","candidate_id":0,'
            '"skill_normalized":"python"},'
            '{"category":"must_have","candidate_id":1,'
            '"skill_normalized":"python"}]}',
        )

    output = await make_parser(httpx.MockTransport(handle)).parse(
        "Python required. Python required."
    )

    assert [item.source_span_start for item in output.requirements] == [0, 17]
