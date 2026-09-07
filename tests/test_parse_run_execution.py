from uuid import UUID, uuid4

import pytest

from careerops.adapters.fake_requirement_parser import FakeRequirementParser
from careerops.domain.errors import RequirementParserError
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
        error_code: ParseRunErrorCode,
        latency_ms: int,
    ) -> bool:
        if parse_run_id != self.work_item.id:
            return False
        self.failed_with = error_code
        return True

    async def commit(self) -> None:
        self.commits += 1


class FailingParser:
    async def parse(self, input_text: str) -> ParserOutput:
        raise RequirementParserError()


class InvalidParser:
    async def parse(self, input_text: str) -> ParserOutput:
        return ParserOutput(
            model_name="invalid-parser",
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
    assert store.commits == 2


@pytest.mark.asyncio
async def test_execution_rejects_output_not_grounded_in_input() -> None:
    store = InMemoryExecutionStore("Python experience required.")

    executed = await ParseRunExecutionService(store, InvalidParser()).execute(store.work_item.id)

    assert executed
    assert store.failed_with == ParseRunErrorCode.PARSER_OUTPUT_INVALID
    assert store.commits == 2
