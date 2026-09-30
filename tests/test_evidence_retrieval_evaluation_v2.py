from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from uuid import UUID

import pytest

from careerops.domain.experiences import ExperienceKind
from careerops.domain.parse_runs import RequirementCategory
from careerops.evaluation.evidence_retrieval import (
    RankedExperience,
    RetrievalEvalExperience,
    RetrievalEvalRequirement,
    to_experience_record,
)
from careerops.evaluation.evidence_retrieval_v2 import (
    DifficultyTag,
    RetrievalProfile,
    RetrievalRelevanceLabel,
    RetrievalSplit,
    RetrievalV2Corpus,
    RetrievalV2Query,
    RetrievalV2QuerySet,
    RetrievalV2ReviewManifest,
    ReviewStatus,
    SupportLevel,
    evaluate_query,
    hit_at_k,
    load_corpus,
    load_query_set,
    precision_at_k,
    recall_at_k,
    validate_acceptance_dataset,
    validate_query_set,
)
from careerops.evaluation.prepare_evidence_retrieval_v2_review import run as prepare_review
from careerops.evaluation.run_evidence_retrieval_v2 import run

FIRST_ID = UUID("40000000-0000-0000-0000-000000000001")
SECOND_ID = UUID("40000000-0000-0000-0000-000000000002")
THIRD_ID = UUID("40000000-0000-0000-0000-000000000003")


def test_checked_in_v2_draft_meets_size_and_difficulty_quotas(tmp_path: Path) -> None:
    base = Path("evals/evidence_retrieval_v2")
    corpus, _ = load_corpus(base / "experiences.json")
    development, _ = load_query_set(base / "development_queries.json", corpus)
    holdout, _ = load_query_set(base / "holdout_queries.json", corpus)

    validate_acceptance_dataset(corpus, development, holdout)
    manifest_path = tmp_path / "review-manifest.json"
    manifest = prepare_review(
        base / "experiences.json",
        base / "development_queries.json",
        base / "holdout_queries.json",
        manifest_path,
    )

    assert manifest.status is ReviewStatus.PENDING_AUTHOR_REVIEW
    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        prepare_review(
            base / "experiences.json",
            base / "development_queries.json",
            base / "holdout_queries.json",
            manifest_path,
        )


def test_validation_requires_grounded_label_quote() -> None:
    corpus = make_corpus()
    query = make_query(
        labels=[
            RetrievalRelevanceLabel(
                experience_id=FIRST_ID,
                support_level=SupportLevel.FULL,
                supporting_quote="Claim that is not in the Experience.",
                rationale="Purposely invalid quote.",
            )
        ]
    )

    with pytest.raises(ValueError, match="quote is not grounded"):
        validate_query_set(make_query_set(query), corpus)


def test_validation_rejects_cross_profile_label() -> None:
    corpus = make_corpus(include_second_profile=True)
    query = make_query(
        labels=[
            RetrievalRelevanceLabel(
                experience_id=THIRD_ID,
                support_level=SupportLevel.PARTIAL,
                supporting_quote="Java service",
                rationale="The ID belongs to another profile.",
            )
        ]
    )

    with pytest.raises(ValueError, match="outside its profile"):
        validate_query_set(make_query_set(query), corpus)


def test_hard_negative_rationale_requires_a_distractor() -> None:
    corpus = make_corpus()
    query = make_query(hard_negative_rationale="Explains a missing distractor.")

    with pytest.raises(ValueError, match="requires a distractor"):
        validate_query_set(make_query_set(query), corpus)


def test_precision_recall_and_hit_use_fixed_cutoffs() -> None:
    irrelevant = UUID("40000000-0000-0000-0000-000000000099")
    ranked = [
        ranked_experience(FIRST_ID, 1),
        ranked_experience(irrelevant, 2),
        ranked_experience(SECOND_ID, 3),
    ]
    relevant = {FIRST_ID, SECOND_ID}

    assert recall_at_k(ranked, relevant, 1) == 0.5
    assert recall_at_k(ranked, relevant, 3) == 1.0
    assert precision_at_k(ranked, relevant, 5) == 0.4
    assert hit_at_k(ranked, relevant, 1) == 1.0
    assert hit_at_k(ranked, relevant, 2) == 1.0


def test_query_metrics_include_mrr_and_negative_abstention() -> None:
    corpus = make_corpus()
    experiences = tuple(
        to_experience_record(item) for item in corpus.profiles[0].experiences
    )
    positive = make_query(
        requirement_text="Java Python",
        skill=None,
        labels=[
            RetrievalRelevanceLabel(
                experience_id=SECOND_ID,
                support_level=SupportLevel.FULL,
                supporting_quote="Python API",
                rationale="Exact Python implementation evidence.",
            )
        ],
    )
    negative = make_query(
        query_id="negative",
        requirement_text="Ruby on Rails",
        skill="ruby",
        labels=[],
        hard_negatives=[FIRST_ID],
        negative_rationale="Neither Experience contains Ruby or Rails evidence.",
    )

    positive_result = evaluate_query(positive, experiences)
    negative_result = evaluate_query(negative, experiences)

    assert positive_result.reciprocal_rank_at_5 == 0.5
    assert positive_result.hit_at_1 == 0.0
    assert positive_result.hit_at_3 == 1.0
    assert negative_result.no_relevant_returned_at_5 is True


def test_cli_refuses_holdout_and_existing_output(tmp_path: Path) -> None:
    corpus = make_corpus()
    development = make_query_set(make_query())
    holdout = make_query_set(make_query(), split=RetrievalSplit.HOLDOUT)
    corpus_path = tmp_path / "corpus.json"
    development_path = tmp_path / "development.json"
    holdout_path = tmp_path / "holdout.json"
    manifest_path = tmp_path / "review-manifest.json"
    output_path = tmp_path / "report.json"
    corpus_path.write_text(corpus.model_dump_json(), encoding="utf-8")
    development_path.write_text(development.model_dump_json(), encoding="utf-8")
    holdout_path.write_text(holdout.model_dump_json(), encoding="utf-8")
    manifest = RetrievalV2ReviewManifest(
        name="test-review",
        version=2,
        status=ReviewStatus.APPROVED_FROZEN,
        reviewer="test author",
        reviewed_at=datetime.now(UTC),
        corpus_sha256=file_sha256(corpus_path),
        development_queries_sha256=file_sha256(development_path),
        holdout_queries_sha256=file_sha256(holdout_path),
        notes=[],
    )
    manifest_path.write_text(manifest.model_dump_json(), encoding="utf-8")

    report = run(corpus_path, development_path, manifest_path, output_path, "test-revision")

    assert report.split is RetrievalSplit.DEVELOPMENT
    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        run(corpus_path, development_path, manifest_path, output_path, "test-revision")
    with pytest.raises(RuntimeError, match="Holdout evaluation is sealed"):
        run(
            corpus_path,
            holdout_path,
            manifest_path,
            tmp_path / "holdout-report.json",
            "test-revision",
        )

    pending_path = tmp_path / "pending-manifest.json"
    pending_path.write_text(
        manifest.model_copy(
            update={
                "status": ReviewStatus.PENDING_AUTHOR_REVIEW,
                "reviewer": None,
                "reviewed_at": None,
            }
        ).model_dump_json(),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="not been approved"):
        run(
            corpus_path,
            development_path,
            pending_path,
            tmp_path / "pending-report.json",
            "test-revision",
        )

    changed_hash_path = tmp_path / "changed-hash-manifest.json"
    changed_hash_path.write_text(
        manifest.model_copy(update={"corpus_sha256": "0" * 64}).model_dump_json(),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="corpus hash does not match"):
        run(
            corpus_path,
            development_path,
            changed_hash_path,
            tmp_path / "changed-hash-report.json",
            "test-revision",
        )


def make_corpus(*, include_second_profile: bool = False) -> RetrievalV2Corpus:
    profiles = [
        RetrievalProfile(
            profile_id="backend",
            description="Backend profile",
            experiences=[
                make_experience(FIRST_ID, "Java service", ["Java"]),
                make_experience(SECOND_ID, "Python API", ["Python"]),
            ],
        )
    ]
    if include_second_profile:
        profiles.append(
            RetrievalProfile(
                profile_id="systems",
                description="Systems profile",
                experiences=[make_experience(THIRD_ID, "Java service", ["Java"])],
            )
        )
    return RetrievalV2Corpus(name="test-corpus", version=2, profiles=profiles)


def make_experience(
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


def make_query(
    *,
    query_id: str = "query",
    requirement_text: str = "Python API",
    skill: str | None = "python",
    labels: list[RetrievalRelevanceLabel] | None = None,
    hard_negatives: list[UUID] | None = None,
    hard_negative_rationale: str | None = None,
    negative_rationale: str | None = None,
) -> RetrievalV2Query:
    resolved_labels = labels
    if resolved_labels is None:
        resolved_labels = [
            RetrievalRelevanceLabel(
                experience_id=SECOND_ID,
                support_level=SupportLevel.FULL,
                supporting_quote="Python API",
                rationale="Direct implementation evidence.",
            )
        ]
    return RetrievalV2Query(
        query_id=query_id,
        profile_id="backend",
        description="Test query",
        requirement=RetrievalEvalRequirement(
            id=UUID("50000000-0000-0000-0000-000000000001"),
            category=RequirementCategory.MUST_HAVE,
            text=requirement_text,
            skill_normalized=skill,
        ),
        labels=resolved_labels,
        hard_negative_experience_ids=hard_negatives or [],
        hard_negative_rationale=hard_negative_rationale,
        negative_rationale=negative_rationale,
        tags=[DifficultyTag.EXACT_SKILL],
    )


def make_query_set(
    query: RetrievalV2Query,
    *,
    split: RetrievalSplit = RetrievalSplit.DEVELOPMENT,
) -> RetrievalV2QuerySet:
    return RetrievalV2QuerySet(
        name="test-queries",
        version=2,
        split=split,
        queries=[query],
    )


def ranked_experience(experience_id: UUID, rank: int) -> RankedExperience:
    return RankedExperience(
        experience_id=experience_id,
        rank=rank,
        score=10 - rank,
        relevant=False,
    )


def file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()
