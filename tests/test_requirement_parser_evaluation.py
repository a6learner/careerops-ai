from pathlib import Path

import pytest

from careerops.domain.errors import ParserOutputValidationError, RequirementParserError
from careerops.domain.parse_runs import (
    ParsedRequirement,
    ParserOutput,
    RequirementCategory,
)
from careerops.evaluation.requirement_parser import (
    LabeledRequirement,
    RequirementEvalCase,
    RequirementEvalCaseResult,
    evaluate_case,
    load_dataset,
    score_case,
    summarize_results,
)


class ProviderFailureParser:
    @property
    def model_name(self) -> str:
        return "provider-failure-parser"

    async def parse(self, input_text: str) -> ParserOutput:
        raise RequirementParserError()


class InvalidOutputParser:
    @property
    def model_name(self) -> str:
        return "invalid-output-parser"

    async def parse(self, input_text: str) -> ParserOutput:
        raise ParserOutputValidationError()


def labeled(
    text: str,
    category: RequirementCategory,
    skill: str | None,
) -> LabeledRequirement:
    return LabeledRequirement(text=text, category=category, skill_normalized=skill)


def test_checked_in_dataset_loads_and_has_unique_case_ids() -> None:
    dataset, dataset_hash = load_dataset(Path("evals/job_requirements_v1.json"))

    assert len(dataset.cases) == 12
    assert len({case.case_id for case in dataset.cases}) == 12
    assert len(dataset_hash) == 64


def test_dataset_rejects_expected_text_that_is_not_grounded(tmp_path: Path) -> None:
    dataset_path = tmp_path / "invalid.json"
    dataset_path.write_text(
        '{"name":"invalid","version":1,"cases":[{'
        '"case_id":"one","description":"invalid label","input_text":"Python required.",'
        '"expected":[{"text":"Java required.","category":"must_have",'
        '"skill_normalized":"java"}]}]}',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="not grounded"):
        load_dataset(dataset_path)


def test_score_case_separates_extraction_category_and_skill_metrics() -> None:
    case = RequirementEvalCase(
        case_id="metrics",
        description="Metric separation",
        input_text="Python required. Redis preferred.",
        expected=[
            labeled("Python required.", RequirementCategory.MUST_HAVE, "python"),
            labeled("Redis preferred.", RequirementCategory.NICE_TO_HAVE, "redis"),
        ],
    )
    output = ParserOutput(
        model_name="test-model",
        requirements=(
            ParsedRequirement(
                category=RequirementCategory.RESPONSIBILITY,
                text="Python required.",
                skill_normalized="python",
                source_span_start=0,
                source_span_end=16,
            ),
            ParsedRequirement(
                category=RequirementCategory.NICE_TO_HAVE,
                text="Redis preferred.",
                skill_normalized=None,
                source_span_start=17,
                source_span_end=33,
            ),
        ),
        input_tokens=10,
        output_tokens=5,
    )

    result = score_case(case, output, latency_ms=20)
    summary = summarize_results([result])

    assert summary.extraction_precision == 1.0
    assert summary.extraction_recall == 1.0
    assert summary.category_accuracy_on_text_matches == 0.5
    assert summary.skill_accuracy_on_text_matches == 0.5
    assert summary.exact_requirement_precision == 0.0
    assert not result.exact_case_match


@pytest.mark.asyncio
async def test_evaluation_records_provider_and_grounding_failures_separately() -> None:
    case = RequirementEvalCase(
        case_id="failure",
        description="Failure accounting",
        input_text="Python required.",
        expected=[labeled("Python required.", RequirementCategory.MUST_HAVE, "python")],
    )

    provider_result = await evaluate_case(case, ProviderFailureParser())
    grounding_result = await evaluate_case(case, InvalidOutputParser())
    summary = summarize_results([provider_result, grounding_result])

    assert summary.provider_failure_count == 1
    assert summary.grounding_failure_count == 1
    assert summary.completed_case_count == 0


def test_summary_counts_false_positive_and_false_negative() -> None:
    result = RequirementEvalCaseResult(
        case_id="counts",
        description="Count accounting",
        expected=[labeled("Python required.", RequirementCategory.MUST_HAVE, "python")],
        predicted=[labeled("Redis required.", RequirementCategory.MUST_HAVE, "redis")],
        expected_count=1,
        predicted_count=1,
        text_matches=0,
        exact_matches=0,
        category_correct=0,
        skill_correct=0,
        exact_case_match=False,
        error_type=None,
        model_name="test-model",
        input_tokens=10,
        output_tokens=5,
        latency_ms=20,
    )

    summary = summarize_results([result])

    assert summary.extraction_precision == 0.0
    assert summary.extraction_recall == 0.0
    assert summary.extraction_f1 == 0.0
    assert summary.total_input_tokens == 10
    assert summary.total_output_tokens == 5
