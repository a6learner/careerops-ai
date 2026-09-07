from time import perf_counter
from typing import Protocol
from uuid import UUID

from careerops.domain.errors import ParserOutputValidationError, RequirementParserError
from careerops.domain.parse_runs import (
    ParsedRequirement,
    ParserOutput,
    ParseRunErrorCode,
    ParseRunWorkItem,
)


class RequirementParser(Protocol):
    async def parse(self, input_text: str) -> ParserOutput: ...


class ParseRunExecutionStore(Protocol):
    async def claim_parse_run(self, parse_run_id: UUID) -> ParseRunWorkItem | None: ...

    async def complete_parse_run(
        self,
        parse_run_id: UUID,
        model_name: str,
        requirements: tuple[ParsedRequirement, ...],
        latency_ms: int,
        input_tokens: int | None,
        output_tokens: int | None,
    ) -> bool: ...

    async def fail_parse_run(
        self,
        parse_run_id: UUID,
        error_code: ParseRunErrorCode,
        latency_ms: int,
    ) -> bool: ...

    async def commit(self) -> None: ...


class ParseRunExecutionService:
    def __init__(self, store: ParseRunExecutionStore, parser: RequirementParser) -> None:
        self._store = store
        self._parser = parser

    async def execute(self, parse_run_id: UUID) -> bool:
        work_item = await self._store.claim_parse_run(parse_run_id)
        if work_item is None:
            return False
        await self._store.commit()

        started = perf_counter()
        try:
            output = await self._parser.parse(work_item.input_text)
            validate_parser_output(work_item.input_text, output)
        except RequirementParserError:
            await self._fail(
                parse_run_id,
                ParseRunErrorCode.PARSER_FAILED,
                elapsed_milliseconds(started),
            )
            return True
        except ParserOutputValidationError:
            await self._fail(
                parse_run_id,
                ParseRunErrorCode.PARSER_OUTPUT_INVALID,
                elapsed_milliseconds(started),
            )
            return True

        completed = await self._store.complete_parse_run(
            parse_run_id=parse_run_id,
            model_name=output.model_name,
            requirements=output.requirements,
            latency_ms=elapsed_milliseconds(started),
            input_tokens=output.input_tokens,
            output_tokens=output.output_tokens,
        )
        if completed:
            await self._store.commit()
        return completed

    async def _fail(
        self,
        parse_run_id: UUID,
        error_code: ParseRunErrorCode,
        latency_ms: int,
    ) -> None:
        failed = await self._store.fail_parse_run(parse_run_id, error_code, latency_ms)
        if failed:
            await self._store.commit()


def validate_parser_output(input_text: str, output: ParserOutput) -> None:
    if output.model_name.strip() == "" or not output.requirements:
        raise ParserOutputValidationError()

    spans: set[tuple[int, int]] = set()
    for requirement in output.requirements:
        span = (requirement.source_span_start, requirement.source_span_end)
        if (
            requirement.text.strip() == ""
            or requirement.source_span_start < 0
            or requirement.source_span_end <= requirement.source_span_start
            or requirement.source_span_end > len(input_text)
            or span in spans
        ):
            raise ParserOutputValidationError()
        source_text = input_text[requirement.source_span_start : requirement.source_span_end]
        if " ".join(source_text.split()) != requirement.text:
            raise ParserOutputValidationError()
        if requirement.skill_normalized is not None and requirement.skill_normalized.strip() == "":
            raise ParserOutputValidationError()
        spans.add(span)


def elapsed_milliseconds(started: float) -> int:
    return int((perf_counter() - started) * 1000)
