from __future__ import annotations

from collections import Counter
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from time import perf_counter

from pydantic import BaseModel, ConfigDict, Field

from careerops.domain.errors import ParserOutputValidationError, RequirementParserError
from careerops.domain.parse_runs import ParserOutput, RequirementCategory
from careerops.services.parse_run_execution import RequirementParser, validate_parser_output


class LabeledRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1)
    category: RequirementCategory
    skill_normalized: str | None


class RequirementEvalCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    input_text: str = Field(min_length=1)
    expected: list[LabeledRequirement] = Field(min_length=1)


class RequirementEvalDataset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    version: int = Field(ge=1)
    cases: list[RequirementEvalCase] = Field(min_length=1)


class RequirementEvalCaseResult(BaseModel):
    case_id: str
    description: str
    expected: list[LabeledRequirement]
    predicted: list[LabeledRequirement]
    expected_count: int
    predicted_count: int
    text_matches: int
    exact_matches: int
    category_correct: int
    skill_correct: int
    exact_case_match: bool
    error_type: str | None
    model_name: str | None
    input_tokens: int | None
    output_tokens: int | None
    latency_ms: int


class RequirementEvalSummary(BaseModel):
    case_count: int
    completed_case_count: int
    provider_failure_count: int
    grounding_failure_count: int
    expected_requirement_count: int
    predicted_requirement_count: int
    text_match_count: int
    exact_match_count: int
    extraction_precision: float
    extraction_recall: float
    extraction_f1: float
    exact_requirement_precision: float
    exact_requirement_recall: float
    exact_requirement_f1: float
    category_accuracy_on_text_matches: float
    skill_accuracy_on_text_matches: float
    exact_case_match_rate: float
    total_input_tokens: int
    total_output_tokens: int
    mean_latency_ms: float


class RequirementEvalReport(BaseModel):
    created_at: datetime
    git_revision: str
    dataset_name: str
    dataset_version: int
    dataset_sha256: str
    provider: str
    configured_model: str
    summary: RequirementEvalSummary
    cases: list[RequirementEvalCaseResult]
    limitations: list[str]


def load_dataset(path: Path) -> tuple[RequirementEvalDataset, str]:
    content = path.read_bytes()
    dataset = RequirementEvalDataset.model_validate_json(content)
    validate_dataset(dataset)
    return dataset, sha256(content).hexdigest()


async def evaluate_dataset(
    dataset: RequirementEvalDataset,
    parser: RequirementParser,
) -> list[RequirementEvalCaseResult]:
    return [await evaluate_case(case, parser) for case in dataset.cases]


async def evaluate_case(
    case: RequirementEvalCase,
    parser: RequirementParser,
) -> RequirementEvalCaseResult:
    started = perf_counter()
    try:
        output = await parser.parse(case.input_text)
        validate_parser_output(case.input_text, output)
    except ParserOutputValidationError:
        return failed_case_result(case, "grounding_or_output_validation", started)
    except RequirementParserError:
        return failed_case_result(case, "provider_failure", started)
    return score_case(case, output, elapsed_milliseconds(started))


def score_case(
    case: RequirementEvalCase,
    output: ParserOutput,
    latency_ms: int,
) -> RequirementEvalCaseResult:
    expected = case.expected
    predicted = [
        LabeledRequirement(
            text=requirement.text,
            category=requirement.category,
            skill_normalized=requirement.skill_normalized,
        )
        for requirement in output.requirements
    ]
    expected_text = Counter(item.text for item in expected)
    predicted_text = Counter(item.text for item in predicted)
    text_matches = sum((expected_text & predicted_text).values())

    expected_exact = Counter(requirement_key(item) for item in expected)
    predicted_exact = Counter(requirement_key(item) for item in predicted)
    exact_matches = sum((expected_exact & predicted_exact).values())

    expected_by_text: dict[str, list[LabeledRequirement]] = {}
    for item in expected:
        expected_by_text.setdefault(item.text, []).append(item)
    category_correct = 0
    skill_correct = 0
    for item in predicted:
        matching_expected = expected_by_text.get(item.text, [])
        if not matching_expected:
            continue
        expected_item = matching_expected.pop(0)
        category_correct += int(item.category == expected_item.category)
        skill_correct += int(item.skill_normalized == expected_item.skill_normalized)

    return RequirementEvalCaseResult(
        case_id=case.case_id,
        description=case.description,
        expected=expected,
        predicted=predicted,
        expected_count=len(expected),
        predicted_count=len(predicted),
        text_matches=text_matches,
        exact_matches=exact_matches,
        category_correct=category_correct,
        skill_correct=skill_correct,
        exact_case_match=expected_exact == predicted_exact,
        error_type=None,
        model_name=output.model_name,
        input_tokens=output.input_tokens,
        output_tokens=output.output_tokens,
        latency_ms=latency_ms,
    )


def failed_case_result(
    case: RequirementEvalCase,
    error_type: str,
    started: float,
) -> RequirementEvalCaseResult:
    return RequirementEvalCaseResult(
        case_id=case.case_id,
        description=case.description,
        expected=case.expected,
        predicted=[],
        expected_count=len(case.expected),
        predicted_count=0,
        text_matches=0,
        exact_matches=0,
        category_correct=0,
        skill_correct=0,
        exact_case_match=False,
        error_type=error_type,
        model_name=None,
        input_tokens=None,
        output_tokens=None,
        latency_ms=elapsed_milliseconds(started),
    )


def summarize_results(results: list[RequirementEvalCaseResult]) -> RequirementEvalSummary:
    case_count = len(results)
    expected_count = sum(item.expected_count for item in results)
    predicted_count = sum(item.predicted_count for item in results)
    text_matches = sum(item.text_matches for item in results)
    exact_matches = sum(item.exact_matches for item in results)
    completed = [item for item in results if item.error_type is None]

    extraction_precision = safe_ratio(text_matches, predicted_count)
    extraction_recall = safe_ratio(text_matches, expected_count)
    exact_precision = safe_ratio(exact_matches, predicted_count)
    exact_recall = safe_ratio(exact_matches, expected_count)
    return RequirementEvalSummary(
        case_count=case_count,
        completed_case_count=len(completed),
        provider_failure_count=sum(item.error_type == "provider_failure" for item in results),
        grounding_failure_count=sum(
            item.error_type == "grounding_or_output_validation" for item in results
        ),
        expected_requirement_count=expected_count,
        predicted_requirement_count=predicted_count,
        text_match_count=text_matches,
        exact_match_count=exact_matches,
        extraction_precision=extraction_precision,
        extraction_recall=extraction_recall,
        extraction_f1=f1(extraction_precision, extraction_recall),
        exact_requirement_precision=exact_precision,
        exact_requirement_recall=exact_recall,
        exact_requirement_f1=f1(exact_precision, exact_recall),
        category_accuracy_on_text_matches=safe_ratio(
            sum(item.category_correct for item in results),
            text_matches,
        ),
        skill_accuracy_on_text_matches=safe_ratio(
            sum(item.skill_correct for item in results),
            text_matches,
        ),
        exact_case_match_rate=safe_ratio(
            sum(item.exact_case_match for item in results),
            case_count,
        ),
        total_input_tokens=sum(item.input_tokens or 0 for item in results),
        total_output_tokens=sum(item.output_tokens or 0 for item in results),
        mean_latency_ms=safe_ratio(sum(item.latency_ms for item in completed), len(completed)),
    )


def requirement_key(item: LabeledRequirement) -> tuple[str, RequirementCategory, str | None]:
    return item.text, item.category, item.skill_normalized


def validate_dataset(dataset: RequirementEvalDataset) -> None:
    case_ids = [case.case_id for case in dataset.cases]
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("Evaluation case IDs must be unique.")
    for case in dataset.cases:
        expected_texts = [item.text for item in case.expected]
        if len(expected_texts) != len(set(expected_texts)):
            raise ValueError(f"Expected texts must be unique in case {case.case_id}.")
        for item in case.expected:
            if item.text not in case.input_text:
                raise ValueError(f"Expected text is not grounded in case {case.case_id}.")
            skill = item.skill_normalized
            if skill is not None and skill != skill.strip().lower():
                raise ValueError(f"Expected skill is not normalized in case {case.case_id}.")


def safe_ratio(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def f1(precision: float, recall: float) -> float:
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def elapsed_milliseconds(started: float) -> int:
    return int((perf_counter() - started) * 1_000)
