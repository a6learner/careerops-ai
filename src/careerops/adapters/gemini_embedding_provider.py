import asyncio
import hashlib
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum

import httpx
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, ValidationError

from careerops.domain.embeddings import EmbeddingOutput
from careerops.domain.errors import EmbeddingProviderError


class EmbeddingProviderFailureCode(StrEnum):
    AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"
    REQUEST_INVALID = "REQUEST_INVALID"
    RATE_LIMITED = "RATE_LIMITED"
    NETWORK_FAILED = "NETWORK_FAILED"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    RESPONSE_INVALID = "RESPONSE_INVALID"
    DIMENSION_INVALID = "DIMENSION_INVALID"
    VECTOR_INVALID = "VECTOR_INVALID"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"


class EmbeddingProviderFailure(Exception):
    def __init__(
        self,
        code: EmbeddingProviderFailureCode,
        *,
        attempts: int,
        status_code: int | None = None,
    ) -> None:
        super().__init__(code.value)
        self.code = code
        self.attempts = attempts
        self.status_code = status_code


@dataclass(frozen=True)
class EmbeddingProviderInput:
    input_sha256: str
    text: str


@dataclass(frozen=True)
class EmbeddingProviderUsage:
    token_count: int | None
    billable_character_count: int | None


@dataclass(frozen=True)
class EmbeddingProviderBatch:
    model_name: str
    vectors: tuple[tuple[float, ...], ...]
    usage: EmbeddingProviderUsage
    request_attempt_count: int


class _EmbeddingPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    values: list[float]


class _UsagePayload(BaseModel):
    model_config = ConfigDict(extra="allow")
    token_count: int | None = Field(
        default=None,
        validation_alias=AliasChoices("tokenCount", "promptTokenCount", "totalTokenCount"),
    )
    billable_character_count: int | None = Field(
        default=None,
        validation_alias=AliasChoices("billableCharacterCount", "billable_character_count"),
    )


class _BatchPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    embeddings: list[_EmbeddingPayload]
    usage_metadata: _UsagePayload | None = Field(default=None, alias="usageMetadata")


class GeminiEmbeddingProvider:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        output_dimensionality: int,
        timeout_seconds: float,
        max_attempts: int = 1,
        retry_base_delay_seconds: float = 1.0,
        base_url: str = "https://generativelanguage.googleapis.com/v1beta",
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        if not api_key:
            raise ValueError("Gemini API key is required.")
        if max_attempts < 1:
            raise ValueError("max_attempts must be positive.")
        self._api_key = api_key
        self._model = model
        self._output_dimensionality = output_dimensionality
        self._timeout_seconds = timeout_seconds
        self._max_attempts = max_attempts
        self._retry_base_delay_seconds = retry_base_delay_seconds
        self._base_url = base_url.rstrip("/")
        self._transport = transport
        self._sleep = sleep

    @property
    def model_name(self) -> str:
        return self._model

    async def embed(self, input_text: str) -> EmbeddingOutput:
        item = EmbeddingProviderInput(
            input_sha256=hashlib.sha256(input_text.encode("utf-8")).hexdigest(),
            text=input_text,
        )
        try:
            batch = await self.embed_batch((item,))
        except EmbeddingProviderFailure as exc:
            raise EmbeddingProviderError() from exc
        return EmbeddingOutput(model_name=batch.model_name, vector=batch.vectors[0])

    async def embed_batch(
        self,
        inputs: tuple[EmbeddingProviderInput, ...],
    ) -> EmbeddingProviderBatch:
        if not inputs:
            return EmbeddingProviderBatch(
                model_name=self._model,
                vectors=(),
                usage=EmbeddingProviderUsage(None, None),
                request_attempt_count=0,
            )
        payload = {
            "requests": [
                {
                    "model": f"models/{self._model}",
                    "content": {"parts": [{"text": item.text}]},
                    "outputDimensionality": self._output_dimensionality,
                }
                for item in inputs
            ]
        }
        headers = {"Content-Type": "application/json", "x-goog-api-key": self._api_key}
        async with httpx.AsyncClient(
            timeout=self._timeout_seconds,
            transport=self._transport,
        ) as client:
            for attempt in range(1, self._max_attempts + 1):
                try:
                    response = await client.post(
                        f"{self._base_url}/models/{self._model}:batchEmbedContents",
                        headers=headers,
                        json=payload,
                    )
                except httpx.TransportError as exc:
                    if attempt == self._max_attempts:
                        raise EmbeddingProviderFailure(
                            EmbeddingProviderFailureCode.NETWORK_FAILED,
                            attempts=attempt,
                        ) from exc
                    await self._sleep(self._retry_delay(attempt))
                    continue
                if response.status_code < 400:
                    return self._parse_response(response, len(inputs), attempt)
                code = classify_status_code(response.status_code)
                if code not in {
                    EmbeddingProviderFailureCode.RATE_LIMITED,
                    EmbeddingProviderFailureCode.PROVIDER_UNAVAILABLE,
                } or attempt == self._max_attempts:
                    raise EmbeddingProviderFailure(
                        code,
                        attempts=attempt,
                        status_code=response.status_code,
                    )
                await self._sleep(self._retry_delay(attempt))
        raise AssertionError("Provider attempt loop exited unexpectedly.")

    def _parse_response(
        self,
        response: httpx.Response,
        expected_count: int,
        attempts: int,
    ) -> EmbeddingProviderBatch:
        try:
            parsed = _BatchPayload.model_validate(response.json())
        except (ValueError, ValidationError) as exc:
            raise EmbeddingProviderFailure(
                EmbeddingProviderFailureCode.RESPONSE_INVALID,
                attempts=attempts,
                status_code=response.status_code,
            ) from exc
        if len(parsed.embeddings) != expected_count:
            raise EmbeddingProviderFailure(
                EmbeddingProviderFailureCode.RESPONSE_INVALID,
                attempts=attempts,
                status_code=response.status_code,
            )
        usage = parsed.usage_metadata
        return EmbeddingProviderBatch(
            model_name=self._model,
            vectors=tuple(tuple(item.values) for item in parsed.embeddings),
            usage=EmbeddingProviderUsage(
                token_count=usage.token_count if usage is not None else None,
                billable_character_count=(
                    usage.billable_character_count if usage is not None else None
                ),
            ),
            request_attempt_count=attempts,
        )

    def _retry_delay(self, attempt: int) -> float:
        return min(self._retry_base_delay_seconds * (2.0 ** (attempt - 1)), 5.0)


GeminiEmbeddingEvaluationProvider = GeminiEmbeddingProvider


def classify_status_code(status_code: int) -> EmbeddingProviderFailureCode:
    if status_code in {401, 403}:
        return EmbeddingProviderFailureCode.AUTHENTICATION_FAILED
    if status_code == 429:
        return EmbeddingProviderFailureCode.RATE_LIMITED
    if status_code in {408, 500, 502, 503, 504}:
        return EmbeddingProviderFailureCode.PROVIDER_UNAVAILABLE
    return EmbeddingProviderFailureCode.REQUEST_INVALID
