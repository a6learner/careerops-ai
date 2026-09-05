from careerops.db.models import Base, Experience, Job, User


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
