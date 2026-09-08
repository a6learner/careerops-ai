from careerops.adapters.fake_requirement_parser import FakeRequirementParser
from careerops.adapters.groq_requirement_parser import GroqRequirementParser
from careerops.core.config import Settings


def create_requirement_parser(
    settings: Settings,
) -> FakeRequirementParser | GroqRequirementParser:
    if settings.llm_provider == "fake":
        return FakeRequirementParser()
    if settings.llm_api_key is None:
        raise RuntimeError("CAREEROPS_LLM_API_KEY is required when the provider is groq.")
    return GroqRequirementParser(
        api_key=settings.llm_api_key.get_secret_value(),
        model=settings.llm_model,
        base_url=settings.llm_base_url,
        timeout_seconds=settings.llm_timeout_seconds,
        max_attempts=settings.llm_max_attempts,
        retry_base_delay_seconds=settings.llm_retry_base_delay_seconds,
        max_output_tokens=settings.llm_max_output_tokens,
    )
