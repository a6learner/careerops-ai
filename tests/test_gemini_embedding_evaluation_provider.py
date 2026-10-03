import json

import httpx
import pytest

from careerops.evaluation.gemini_embedding_provider import (
    EmbeddingProviderFailure,
    EmbeddingProviderFailureCode,
    EmbeddingProviderInput,
    GeminiEmbeddingEvaluationProvider,
)


def make_provider(transport: httpx.MockTransport) -> GeminiEmbeddingEvaluationProvider:
    return GeminiEmbeddingEvaluationProvider(
        api_key="test-key",
        model="gemini-embedding-2",
        output_dimensionality=1536,
        timeout_seconds=1.0,
        max_attempts=1,
        base_url="https://gemini.test/v1beta/",
        transport=transport,
    )


@pytest.mark.asyncio
async def test_gemini_batch_request_is_budgeted_and_parses_usage() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert request.url == (
            "https://gemini.test/v1beta/models/gemini-embedding-2:batchEmbedContents"
        )
        assert request.headers["x-goog-api-key"] == "test-key"
        assert [item["content"]["parts"][0]["text"] for item in body["requests"]] == [
            "first",
            "second",
        ]
        assert all(item["outputDimensionality"] == 1536 for item in body["requests"])
        return httpx.Response(
            200,
            request=request,
            json={
                "embeddings": [{"values": [1.0]}, {"values": [2.0]}],
                "usageMetadata": {"tokenCount": 7, "billableCharacterCount": 12},
            },
        )

    batch = await make_provider(httpx.MockTransport(handle)).embed_batch(
        (
            EmbeddingProviderInput("a" * 64, "first"),
            EmbeddingProviderInput("b" * 64, "second"),
        )
    )

    assert batch.vectors == ((1.0,), (2.0,))
    assert batch.usage.token_count == 7
    assert batch.usage.billable_character_count == 12
    assert batch.request_attempt_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status_code", "expected"),
    [
        (400, EmbeddingProviderFailureCode.REQUEST_INVALID),
        (401, EmbeddingProviderFailureCode.AUTHENTICATION_FAILED),
        (403, EmbeddingProviderFailureCode.AUTHENTICATION_FAILED),
        (429, EmbeddingProviderFailureCode.RATE_LIMITED),
        (503, EmbeddingProviderFailureCode.PROVIDER_UNAVAILABLE),
    ],
)
async def test_gemini_provider_classifies_http_failures(
    status_code: int,
    expected: EmbeddingProviderFailureCode,
) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, request=request)

    with pytest.raises(EmbeddingProviderFailure) as captured:
        await make_provider(httpx.MockTransport(handle)).embed_batch(
            (EmbeddingProviderInput("a" * 64, "input"),)
        )

    assert captured.value.code is expected
    assert captured.value.attempts == 1


@pytest.mark.asyncio
async def test_gemini_provider_rejects_partial_batch_response() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, request=request, json={"embeddings": [{"values": [1.0]}]})

    with pytest.raises(EmbeddingProviderFailure) as captured:
        await make_provider(httpx.MockTransport(handle)).embed_batch(
            (
                EmbeddingProviderInput("a" * 64, "first"),
                EmbeddingProviderInput("b" * 64, "second"),
            )
        )

    assert captured.value.code is EmbeddingProviderFailureCode.RESPONSE_INVALID


@pytest.mark.asyncio
async def test_gemini_provider_classifies_transport_failure_without_retry() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    with pytest.raises(EmbeddingProviderFailure) as captured:
        await make_provider(httpx.MockTransport(handle)).embed_batch(
            (EmbeddingProviderInput("a" * 64, "input"),)
        )

    assert captured.value.code is EmbeddingProviderFailureCode.NETWORK_FAILED
    assert captured.value.attempts == 1
