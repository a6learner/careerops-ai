from pathlib import Path
from uuid import UUID

import pytest

from careerops.domain.experiences import ExperienceKind
from careerops.domain.parse_runs import RequirementCategory
from careerops.evaluation.evidence_retrieval import (
    RetrievalEvalCase,
    RetrievalEvalCaseResult,
    RetrievalEvalDataset,
    RetrievalEvalExperience,
    RetrievalEvalRequirement,
    evaluate_case,
    load_dataset,
    summarize_results,
    to_experience_record,
    validate_dataset,
)
from careerops.evaluation.run_evidence_retrieval import run


def test_checked_in_retrieval_dataset_is_versioned_and_valid() -> None:
    dataset, dataset_hash = load_dataset(Path("evals/evidence_retrieval_v1.json"))

    assert dataset.version == 1
    assert 20 <= len(dataset.cases) <= 30
    assert any(case.relevant_experience_ids for case in dataset.cases)
    assert any(not case.relevant_experience_ids for case in dataset.cases)
    assert len(dataset_hash) == 64


def test_dataset_rejects_unknown_relevant_experience(tmp_path: Path) -> None:
    path = tmp_path / "invalid.json"
    path.write_text(
        '{"name":"invalid","version":1,"experiences":[{'
        '"id":"00000000-0000-0000-0000-000000000001","title":"One",'
        '"kind":"project","description":"Python API","skills":["Python"],'
        '"outcome":null}],"cases":[{"case_id":"one","description":"invalid",'
        '"requirement":{"id":"10000000-0000-0000-0000-000000000001",'
        '"category":"must_have","text":"Python","skill_normalized":"python"},'
        '"relevant_experience_ids":["00000000-0000-0000-0000-000000000099"]}]}',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unknown Experience ID"):
        load_dataset(path)


def test_dataset_rejects_duplicate_experience_ids() -> None:
    duplicated = experience(
        UUID("00000000-0000-0000-0000-000000000001"),
        "Python API",
        ["Python"],
    )
    dataset = RetrievalEvalDataset(
        name="duplicates",
        version=1,
        experiences=[duplicated, duplicated],
        cases=[retrieval_case("Python", "python", [duplicated.id])],
    )

    with pytest.raises(ValueError, match="Experience IDs must be unique"):
        validate_dataset(dataset)


def test_metrics_use_macro_recall_and_first_relevant_rank() -> None:
    first = UUID("00000000-0000-0000-0000-000000000001")
    second = UUID("00000000-0000-0000-0000-000000000002")
    irrelevant = UUID("00000000-0000-0000-0000-000000000003")
    experiences = tuple(
        to_experience_record(item)
        for item in (
            experience(first, "Python API", ["Python"]),
            experience(second, "Backend service", ["Python"]),
            experience(irrelevant, "API documentation", ["Writing"]),
        )
    )
    case = retrieval_case("Python API", "python", [first, second])

    result = evaluate_case(case, experiences)

    assert result.recall_at_1 == 0.5
    assert result.recall_at_3 == 1.0
    assert result.reciprocal_rank_at_5 == 1.0


def test_negative_query_accuracy_requires_an_empty_ranking() -> None:
    experiences = (
        to_experience_record(
            experience(
                UUID("00000000-0000-0000-0000-000000000001"),
                "Python API",
                ["Python"],
            )
        ),
    )
    empty_result = evaluate_case(retrieval_case("Ruby on Rails", "ruby", []), experiences)
    noisy_result = evaluate_case(retrieval_case("Build API", None, []), experiences)
    summary = summarize_results([empty_result, noisy_result])

    assert empty_result.no_relevant_returned_at_5 is True
    assert noisy_result.no_relevant_returned_at_5 is False
    assert summary.no_relevant_returned_accuracy_at_5 == 0.5
    assert summary.positive_query_count == 0


def test_summary_macro_averages_positive_query_metrics() -> None:
    summary = summarize_results(
        [positive_result("first", 1.0, 1.0), positive_result("second", 0.5, 0.25)]
    )

    assert summary.recall_at_1 == 0.75
    assert summary.recall_at_3 == 0.75
    assert summary.recall_at_5 == 0.75
    assert summary.mrr_at_5 == 0.625


def test_report_writer_refuses_to_overwrite_evidence(tmp_path: Path) -> None:
    output = tmp_path / "report.json"
    report = run(Path("evals/evidence_retrieval_v1.json"), output, "test-revision")

    assert report.git_revision == "test-revision"
    assert report.summary.query_count >= 20
    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        run(Path("evals/evidence_retrieval_v1.json"), output, "test-revision")


def experience(
    experience_id: UUID,
    description: str,
    skills: list[str],
) -> RetrievalEvalExperience:
    return RetrievalEvalExperience(
        id=experience_id,
        title="Project",
        kind=ExperienceKind.PROJECT,
        description=description,
        skills=skills,
        outcome=None,
    )


def retrieval_case(
    text: str,
    skill: str | None,
    relevant_ids: list[UUID],
) -> RetrievalEvalCase:
    return RetrievalEvalCase(
        case_id="metrics",
        description="Metric behavior",
        requirement=RetrievalEvalRequirement(
            id=UUID("10000000-0000-0000-0000-000000000001"),
            category=RequirementCategory.MUST_HAVE,
            text=text,
            skill_normalized=skill,
        ),
        relevant_experience_ids=relevant_ids,
    )


def positive_result(
    case_id: str,
    recall: float,
    reciprocal_rank: float,
) -> RetrievalEvalCaseResult:
    return RetrievalEvalCaseResult(
        case_id=case_id,
        description="Positive result",
        relevant_experience_ids=[UUID("00000000-0000-0000-0000-000000000001")],
        ranked_experiences=[],
        recall_at_1=recall,
        recall_at_3=recall,
        recall_at_5=recall,
        reciprocal_rank_at_5=reciprocal_rank,
        no_relevant_returned_at_5=None,
    )
