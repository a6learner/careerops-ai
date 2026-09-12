from careerops.db.models import (
    AnalysisRun,
    Base,
    EvidenceMatch,
    Experience,
    Job,
    JobRequirement,
    ParseRun,
    User,
)


def test_users_table_metadata_matches_initial_migration_contract() -> None:
    users = Base.metadata.tables["users"]

    assert User.__tablename__ == "users"
    assert set(users.columns.keys()) == {"id", "email", "password_hash", "created_at"}
    assert users.columns["id"].primary_key
    assert not users.columns["email"].nullable
    assert not users.columns["password_hash"].nullable
    assert not users.columns["created_at"].nullable


def test_experiences_table_metadata_matches_migration_contract() -> None:
    experiences = Base.metadata.tables["experiences"]

    assert Experience.__tablename__ == "experiences"
    assert set(experiences.columns.keys()) == {
        "id",
        "user_id",
        "title",
        "kind",
        "description",
        "skills",
        "outcome",
        "version",
        "content_hash",
        "embedding",
        "deleted_at",
        "created_at",
        "updated_at",
    }
    assert experiences.columns["id"].primary_key
    assert not experiences.columns["user_id"].nullable
    assert not experiences.columns["title"].nullable
    assert not experiences.columns["kind"].nullable
    assert not experiences.columns["description"].nullable
    assert not experiences.columns["skills"].nullable
    assert not experiences.columns["version"].nullable
    assert not experiences.columns["content_hash"].nullable
    assert experiences.columns["embedding"].nullable
    assert experiences.columns["deleted_at"].nullable


def test_jobs_table_metadata_matches_migration_contract() -> None:
    jobs = Base.metadata.tables["jobs"]

    assert Job.__tablename__ == "jobs"
    assert set(jobs.columns.keys()) == {
        "id",
        "user_id",
        "company",
        "title",
        "raw_description",
        "description_hash",
        "source_url",
        "location",
        "deadline",
        "status",
        "version",
        "deleted_at",
        "created_at",
        "updated_at",
    }
    assert jobs.columns["id"].primary_key
    assert not jobs.columns["user_id"].nullable
    assert not jobs.columns["company"].nullable
    assert not jobs.columns["title"].nullable
    assert not jobs.columns["raw_description"].nullable
    assert not jobs.columns["description_hash"].nullable
    assert jobs.columns["source_url"].nullable
    assert jobs.columns["location"].nullable
    assert jobs.columns["deadline"].nullable
    assert not jobs.columns["status"].nullable
    assert not jobs.columns["version"].nullable
    assert jobs.columns["deleted_at"].nullable


def test_parse_runs_table_metadata_matches_migration_contract() -> None:
    parse_runs = Base.metadata.tables["parse_runs"]

    assert ParseRun.__tablename__ == "parse_runs"
    assert set(parse_runs.columns.keys()) == {
        "id",
        "user_id",
        "job_id",
        "status",
        "idempotency_key",
        "input_fingerprint",
        "input_text",
        "model_name",
        "prompt_version",
        "attempt",
        "error_code",
        "latency_ms",
        "input_tokens",
        "output_tokens",
        "started_at",
        "finished_at",
        "created_at",
    }
    assert parse_runs.columns["id"].primary_key
    assert not parse_runs.columns["user_id"].nullable
    assert not parse_runs.columns["job_id"].nullable
    assert not parse_runs.columns["status"].nullable
    assert not parse_runs.columns["idempotency_key"].nullable
    assert not parse_runs.columns["input_fingerprint"].nullable
    assert not parse_runs.columns["input_text"].nullable
    assert not parse_runs.columns["model_name"].nullable
    assert not parse_runs.columns["prompt_version"].nullable
    idempotency_index = next(
        index for index in parse_runs.indexes if index.name == "uq_parse_runs_user_job_idempotency"
    )
    assert idempotency_index.unique
    assert [column.name for column in idempotency_index.columns] == [
        "user_id",
        "job_id",
        "idempotency_key",
    ]
    constraint_names = {constraint.name for constraint in parse_runs.constraints}
    assert "ck_parse_runs_lifecycle" in constraint_names


def test_job_requirements_table_metadata_matches_migration_contract() -> None:
    requirements = Base.metadata.tables["job_requirements"]

    assert JobRequirement.__tablename__ == "job_requirements"
    assert set(requirements.columns.keys()) == {
        "id",
        "job_id",
        "parse_run_id",
        "category",
        "text",
        "skill_normalized",
        "source_span_start",
        "source_span_end",
    }
    assert requirements.columns["id"].primary_key
    assert not requirements.columns["job_id"].nullable
    assert not requirements.columns["parse_run_id"].nullable
    assert not requirements.columns["category"].nullable
    assert not requirements.columns["text"].nullable
    assert requirements.columns["skill_normalized"].nullable
    assert requirements.columns["source_span_start"].nullable
    assert requirements.columns["source_span_end"].nullable


def test_analysis_runs_table_metadata_matches_migration_contract() -> None:
    analysis_runs = Base.metadata.tables["analysis_runs"]

    assert AnalysisRun.__tablename__ == "analysis_runs"
    assert set(analysis_runs.columns.keys()) == {
        "id",
        "user_id",
        "job_id",
        "parse_run_id",
        "status",
        "idempotency_key",
        "input_fingerprint",
        "model_name",
        "prompt_version",
        "attempt",
        "validation_failure_count",
        "error_code",
        "latency_ms",
        "input_tokens",
        "output_tokens",
        "started_at",
        "finished_at",
        "created_at",
    }
    assert analysis_runs.columns["id"].primary_key
    assert not analysis_runs.columns["parse_run_id"].nullable
    assert not analysis_runs.columns["validation_failure_count"].nullable
    constraint_names = {constraint.name for constraint in analysis_runs.constraints}
    assert "ck_analysis_runs_validation_failure_count" in constraint_names


def test_evidence_matches_table_metadata_enforces_grounding_contract() -> None:
    evidence_matches = Base.metadata.tables["evidence_matches"]

    assert EvidenceMatch.__tablename__ == "evidence_matches"
    assert set(evidence_matches.columns.keys()) == {
        "id",
        "analysis_run_id",
        "requirement_id",
        "experience_id",
        "experience_version",
        "verdict",
        "quote",
        "quote_valid",
        "confidence",
    }
    assert evidence_matches.columns["id"].primary_key
    assert not evidence_matches.columns["analysis_run_id"].nullable
    assert not evidence_matches.columns["requirement_id"].nullable
    assert evidence_matches.columns["experience_id"].nullable
    assert evidence_matches.columns["experience_version"].nullable
    assert evidence_matches.columns["quote"].nullable
    assert not evidence_matches.columns["quote_valid"].nullable
    constraint_names = {constraint.name for constraint in evidence_matches.constraints}
    assert "ck_evidence_matches_grounded_verdict" in constraint_names
    assert "ck_evidence_matches_confidence" in constraint_names
    indexes = {index.name: index for index in evidence_matches.indexes}
    assert indexes["uq_evidence_matches_run_requirement"].unique
