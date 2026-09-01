from careerops.db.models import Base, User


def test_users_table_metadata_matches_initial_migration_contract() -> None:
    users = Base.metadata.tables["users"]

    assert User.__tablename__ == "users"
    assert set(users.columns.keys()) == {"id", "email", "password_hash", "created_at"}
    assert users.columns["id"].primary_key
    assert not users.columns["email"].nullable
    assert not users.columns["password_hash"].nullable
    assert not users.columns["created_at"].nullable
