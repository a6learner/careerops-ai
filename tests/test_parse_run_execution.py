import logging
from uuid import UUID, uuid4

import pytest

from careerops.adapters.fake_requirement_parser import FakeRequirementParser
from careerops.domain.errors import (
    ParserOutputFailureReason,
    ParserOutputValidationError,
    RequirementParserError,
)
from careerops.domain.parse_runs import (
    ParsedRequirement,
    ParserOutput,
    ParseRunErrorCode,
    ParseRunWorkItem,
    RequirementCategory,
)
from careerops.services.parse_run_execution import ParseRunExecutionService


class InMemoryExecutionStore:
    def __init__(self, input_text: str) -> None:
        self.work_item = ParseRunWorkItem(id=uuid4(), input_text=input_text)
        self.claimed = False
        self.commits = 0
        self.completed_requirements: tuple[ParsedRequirement, ...] = ()
        self.failed_with: ParseRunErrorCode | None = None
        self.failed_model_name: str | None = None
        self.failed_tokens: tuple[int | None, int | None] | None = None

    async def claim_parse_run(self, parse_run_id: UUID) -> ParseRunWorkItem | None:
        if self.claimed or parse_run_id != self.work_item.id:
            return None
        self.claimed = True
        return self.work_item

    async def complete_parse_run(
        self,
        parse_run_id: UUID,
        model_name: str,
        requirements: tuple[ParsedRequirement, ...],
        latency_ms: int,
        input_tokens: int | None,
        output_tokens: int | None,
    ) -> bool:
        if parse_run_id != self.work_item.id:
            return False
        self.completed_requirements = requirements
        return True

    async def fail_parse_run(
        self,
        parse_run_id: UUID,
        model_name: str,
        error_code: ParseRunErrorCode,
        latency_ms: int,
        *,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
    ) -> bool:
        if parse_run_id != self.work_item.id:
            return False
        self.failed_model_name = model_name
        self.failed_with = error_code
        self.failed_tokens = (input_tokens, output_tokens)
        return True

    async def commit(self) -> None:
        self.commits += 1


class FailingParser:
    @property
    def model_name(self) -> str:
        return "failing-parser"

    async def parse(self, input_text: str) -> ParserOutput:
        raise RequirementParserError()


class RejectedOutputParser:
    @property
    def model_name(self) -> str:
        return "rejected-parser"

    async def parse(self, input_text: str) -> ParserOutput:
        raise ParserOutputValidationError(
            ParserOutputFailureReason.UNKNOWN_CANDIDATE, input_tokens=120, output_tokens=30
        )


class InvalidParser:
    @property
    def model_name(self) -> str:
        return "invalid-parser"

    async def parse(self, input_text: str) -> ParserOutput:
        return ParserOutput(
            model_name="invalid-parser",
            input_tokens=11,
            output_tokens=5,
            requirements=(
                ParsedRequirement(
                    category=RequirementCategory.MUST_HAVE,
                    text="not in source",
                    skill_normalized=None,
                    source_span_start=0,
                    source_span_end=3,
                ),
            ),
        )


@pytest.mark.asyncio
async def test_execution_claims_and_completes_once() -> None:
    store = InMemoryExecutionStore("Python experience required.")
    service = ParseRunExecutionService(store, FakeRequirementParser())

    first = await service.execute(store.work_item.id)
    duplicate = await service.execute(store.work_item.id)

    assert first
    assert not duplicate
    assert len(store.completed_requirements) == 1
    assert store.failed_with is None
    assert store.commits == 2


@pytest.mark.asyncio
async def test_execution_records_provider_failure() -> None:
    store = InMemoryExecutionStore("Python experience required.")

    executed = await ParseRunExecutionService(store, FailingParser()).execute(store.work_item.id)

    assert executed
    assert store.failed_with == ParseRunErrorCode.PARSER_FAILED
    assert store.failed_model_name == "failing-parser"
    assert store.commits == 2


@pytest.mark.asyncio
async def test_execution_rejects_output_not_grounded_in_input() -> None:
    store = InMemoryExecutionStore("Python experience required.")

    executed = await ParseRunExecutionService(store, InvalidParser()).execute(store.work_item.id)

    assert executed
    assert store.failed_with == ParseRunErrorCode.PARSER_OUTPUT_INVALID
    assert store.failed_tokens == (11, 5)
    assert store.commits == 2


@pytest.mark.asyncio
async def test_execution_records_rejected_output_reason_and_token_usage(
    caplog: pytest.LogCaptureFixture,
) -> None:
    store = InMemoryExecutionStore("Python experience required.")

    with caplog.at_level(logging.WARNING):
        executed = await ParseRunExecutionService(store, RejectedOutputParser()).execute(
            store.work_item.id
        )

    assert executed
    assert store.failed_with == ParseRunErrorCode.PARSER_OUTPUT_INVALID
    assert store.failed_tokens == (120, 30)
    rejected = [r for r in caplog.records if r.getMessage() == "requirement_parser_output_rejected"]
    assert len(rejected) == 1
    assert rejected[0].__dict__["failure_reason"] == "unknown_candidate"
