import os
from time import perf_counter

import pytest

from careerops.adapters.factory import create_requirement_parser
from careerops.core.config import get_settings
from careerops.services.parse_run_execution import validate_parser_output

pytestmark = pytest.mark.integration


@pytest.mark.skipif(
    os.getenv("CAREEROPS_RUN_LLM_INTEGRATION") != "1",
    reason="requires an explicitly enabled real Groq API request",
)
@pytest.mark.asyncio
async def test_groq_returns_grounded_requirements() -> None:
    settings = get_settings()
    assert settings.llm_provider == "groq"
    input_text = (
        "Candidates must have Python experience. "
        "Experience with PostgreSQL is preferred. "
        "Build and operate reliable backend APIs."
    )

    started = perf_counter()
    output = await create_requirement_parser(settings).parse(input_text)
    latency_ms = int((perf_counter() - started) * 1_000)

    validate_parser_output(input_text, output)
    assert len(output.requirements) >= 2
    assert output.input_tokens is not None
    assert output.output_tokens is not None
    print(
        f"model={output.model_name} requirements={len(output.requirements)} "
        f"input_tokens={output.input_tokens} output_tokens={output.output_tokens} "
        f"latency_ms={latency_ms}"
    )
