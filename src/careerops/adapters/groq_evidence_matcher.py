import asyncio
import json
from collections.abc import Awaitable, Callable
from time import monotonic
from typing import Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from careerops.adapters.evidence_matcher_schema import (
    evidence_matcher_instructions,
    matcher_output_validation_error,
    parse_matcher_response,
)
from careerops.adapters.groq_chat import (
    GroqChatTransport,
    GroqRequestError,
    GroqRequestFailureReason,
)
from careerops.domain.analysis_runs import EvidenceMatcherOutput
from careerops.domain.errors import (
    EvidenceMatcherError,
    EvidenceMatcherFailureReason,
    MatcherOutputFailureReason,
)
from careerops.domain.evidence_matching import (
    MATCHER_SCHEMA_VERSION,
    EvidenceMatcherInput,
)


class _EvidenceReferencePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    experience_id: str
    experience_version: int
    source_ref: str
    quote: str


class _MatchPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requirement_id: str
    verdict: Literal["matched", "partial", "missing", "insufficient_evidence"]
    evidence: _EvidenceReferencePayload | None
    confidence: float = Field(ge=0.0, le=1.0, allow_inf_nan=False)


class _MatcherPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["evidence-matcher-schema-v1"]
    matches: list[_MatchPayload]


class _MessagePayload(BaseModel):
    content: str


class _ChoicePayload(BaseModel):
    message: _MessagePayload


class _UsagePayload(BaseModel):
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


class _ChatCompletionPayload(BaseModel):
    model: str | None = None
    choices: list[_ChoicePayload] = Field(min_length=1)
    usage: _UsagePayload | None = None


class GroqEvidenceMatcher:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str,
        timeout_seconds: float,
        max_attempts: int,
        retry_base_delay_seconds: float,
        max_output_tokens: int,
        minimum_request_interval_seconds: float = 0.0,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self._model = model
        self._max_output_tokens = max_output_tokens
        self._minimum_request_interval_seconds = minimum_request_interval_seconds
        self._sleep = sleep
        self._clock = clock
        self._last_request_started_at: float | None = None
        self._chat = GroqChatTransport(
            api_key=api_key,
            base_url=base_url,
            timeout_seconds=timeout_seconds,
            max_attempts=max_attempts,
            retry_base_delay_seconds=retry_base_delay_seconds,
            transport=transport,
            sleep=sleep,
        )

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def request_attempt_count(self) -> int:
        return self._chat.request_attempt_count

    async def match(self, matcher_input: EvidenceMatcherInput) -> EvidenceMatcherOutput:
        await self._pace_request()
        payload: dict[str, object] = {
            "model": self._model,
            "messages": [
                {
                    "role": "system",
                    "content": evidence_matcher_instructions(matcher_input.prompt_version),
                },
                {
                    "role": "user",
                    "content": json.dumps(matcher_input_payload(matcher_input)),
                },
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "evidence_matches",
                    "strict": True,
                    "schema": groq_matcher_response_json_schema(),
                },
            },
            "reasoning_effort": "low",
            "temperature": 0.0,
            "max_completion_tokens": self._max_output_tokens,
        }
        try:
            response = await self._chat.post_chat_completion(payload)
        except GroqRequestError as exc:
            raise EvidenceMatcherError(matcher_failure_reason(exc.reason)) from exc
        try:
            completion = _ChatCompletionPayload.model_validate(response.json())
        except (ValueError, ValidationError) as exc:
            raise EvidenceMatcherError(EvidenceMatcherFailureReason.REQUEST_FAILED) from exc

        content = completion.choices[0].message.content
        usage = completion.usage
        input_tokens = usage.prompt_tokens if usage is not None else None
        output_tokens = usage.completion_tokens if usage is not None else None
        try:
            raw_payload = json.loads(content)
        except json.JSONDecodeError as exc:
            raise matcher_output_validation_error(
                MatcherOutputFailureReason.INVALID_JSON,
                content=content,
                validation_error=exc,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            ) from exc
        try:
            provider_payload = _MatcherPayload.model_validate(raw_payload)
        except ValidationError as exc:
            raise matcher_output_validation_error(
                MatcherOutputFailureReason.INVALID_SCHEMA,
                content=content,
                validation_error=exc,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            ) from exc

        normalized_matches: list[dict[str, object]] = []
        for match in provider_payload.matches:
            normalized: dict[str, object] = {
                "requirement_id": match.requirement_id,
                "verdict": match.verdict,
                "confidence": match.confidence,
            }
            if match.evidence is not None:
                normalized["evidence"] = match.evidence.model_dump()
            normalized_matches.append(normalized)
        return parse_matcher_response(
            json.dumps(
                {
                    "schema_version": provider_payload.schema_version,
                    "matches": normalized_matches,
                }
            ),
            model_name=completion.model or self._model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    async def _pace_request(self) -> None:
        if self._last_request_started_at is not None:
            elapsed = self._clock() - self._last_request_started_at
            delay = self._minimum_request_interval_seconds - elapsed
            if delay > 0:
                await self._sleep(delay)
        self._last_request_started_at = self._clock()


def matcher_input_payload(matcher_input: EvidenceMatcherInput) -> dict[str, object]:
    return {
        "schema_version": matcher_input.schema_version,
        "prompt_version": matcher_input.prompt_version,
        "requirements": [
            {
                "requirement_id": str(requirement.requirement_id),
                "category": requirement.category.value,
                "text": requirement.text,
                "skill_normalized": requirement.skill_normalized,
            }
            for requirement in matcher_input.requirements
        ],
        "experiences": [
            {
                "experience_id": str(experience.experience_id),
                "experience_version": experience.experience_version,
                "sources": [
                    {"source_ref": source.source_ref, "text": source.text}
                    for source in experience.sources
                ],
            }
            for experience in matcher_input.experiences
        ],
        "candidate_sets": [
            {
                "requirement_id": str(candidate_set.requirement_id),
                "candidates": [
                    {
                        "experience_id": str(candidate.experience_id),
                        "rank": candidate.rank,
                    }
                    for candidate in candidate_set.candidates
                ],
            }
            for candidate_set in matcher_input.candidate_sets
        ],
    }


def groq_matcher_response_json_schema() -> dict[str, object]:
    evidence_schema: dict[str, object] = {
        "type": "object",
        "properties": {
            "experience_id": {"type": "string"},
            "experience_version": {"type": "integer"},
            "source_ref": {"type": "string"},
            "quote": {"type": "string"},
        },
        "required": [
            "experience_id",
            "experience_version",
            "source_ref",
            "quote",
        ],
        "additionalProperties": False,
    }
    common_properties: dict[str, object] = {
        "requirement_id": {"type": "string"},
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
    }
    positive_match_schema: dict[str, object] = {
        "type": "object",
        "properties": {
            **common_properties,
            "verdict": {
                "type": "string",
                "enum": ["matched", "partial"],
            },
            "evidence": evidence_schema,
        },
        "required": ["requirement_id", "verdict", "evidence", "confidence"],
        "additionalProperties": False,
    }
    gap_match_schema: dict[str, object] = {
        "type": "object",
        "properties": {
            **common_properties,
            "verdict": {
                "type": "string",
                "enum": ["missing", "insufficient_evidence"],
            },
            "evidence": {"type": "null"},
        },
        "required": ["requirement_id", "verdict", "evidence", "confidence"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {
            "schema_version": {"type": "string", "enum": [MATCHER_SCHEMA_VERSION]},
            "matches": {
                "type": "array",
                "items": {"anyOf": [positive_match_schema, gap_match_schema]},
            },
        },
        "required": ["schema_version", "matches"],
        "additionalProperties": False,
    }


def matcher_failure_reason(reason: GroqRequestFailureReason) -> EvidenceMatcherFailureReason:
    return {
        GroqRequestFailureReason.REQUEST_FAILED: EvidenceMatcherFailureReason.REQUEST_FAILED,
        GroqRequestFailureReason.MISCONFIGURED: EvidenceMatcherFailureReason.MISCONFIGURED,
        GroqRequestFailureReason.TIMEOUT: EvidenceMatcherFailureReason.TIMEOUT,
        GroqRequestFailureReason.RATE_LIMITED: EvidenceMatcherFailureReason.RATE_LIMITED,
        GroqRequestFailureReason.UNAVAILABLE: EvidenceMatcherFailureReason.UNAVAILABLE,
    }[reason]
