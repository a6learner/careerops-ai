import pytest
from pydantic import ValidationError

from careerops.core.config import DEFAULT_LOCAL_JWT_SECRET, Settings


def test_local_environment_keeps_documented_development_secret() -> None:
    settings = Settings(_env_file=None)

    assert settings.environment == "local"
    assert settings.jwt_secret == DEFAULT_LOCAL_JWT_SECRET


def test_production_rejects_documented_development_secret() -> None:
    with pytest.raises(ValidationError, match="production requires an explicit"):
        Settings(
            _env_file=None,
            CAREEROPS_ENV="production",
            jwt_secret=DEFAULT_LOCAL_JWT_SECRET,
        )


def test_production_accepts_explicit_secret() -> None:
    settings = Settings(
        _env_file=None,
        CAREEROPS_ENV="production",
        jwt_secret="deployment-specific-secret-that-is-not-checked-in",
    )

    assert settings.environment == "production"
