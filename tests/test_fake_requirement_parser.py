import pytest

from careerops.adapters.fake_requirement_parser import FakeRequirementParser
from careerops.domain.parse_runs import FAKE_PARSE_MODEL_NAME, RequirementCategory


@pytest.mark.asyncio
async def test_fake_parser_returns_requirements_with_source_spans() -> None:
    input_text = "Python experience required. Preferred Redis."

    output = await FakeRequirementParser().parse(input_text)

    assert output.model_name == FAKE_PARSE_MODEL_NAME
    assert [requirement.text for requirement in output.requirements] == [
        "Python experience required",
        "Preferred Redis",
    ]
    assert output.requirements[0].category == RequirementCategory.MUST_HAVE
    assert output.requirements[1].category == RequirementCategory.NICE_TO_HAVE
    assert output.requirements[0].skill_normalized == "python"
    first = output.requirements[0]
    source_text = input_text[first.source_span_start : first.source_span_end]
    assert " ".join(source_text.split()) == first.text
