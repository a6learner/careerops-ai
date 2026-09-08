import pytest

from careerops.adapters.factory import create_requirement_parser
from careerops.adapters.fake_requirement_parser import FakeRequirementParser
from careerops.adapters.groq_requirement_parser import GroqRequirementParser
from careerops.core.config import Settings


def test_factory_uses_fake_parser_by_default() -> None:
    settings = Settings(_env_file=None)

    assert isinstance(create_requirement_parser(settings), FakeRequirementParser)


def test_factory_builds_groq_parser_when_configured() -> None:
    settings = Settings(
        _env_file=None,
        llm_provider="groq",
        llm_api_key="test-key",
    )

    assert isinstance(create_requirement_parser(settings), GroqRequirementParser)


def test_factory_requires_key_for_groq() -> None:
    settings = Settings(_env_file=None, llm_provider="groq")

    with pytest.raises(RuntimeError, match="CAREEROPS_LLM_API_KEY"):
        create_requirement_parser(settings)
