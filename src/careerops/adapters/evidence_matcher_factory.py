import os

from careerops.adapters.fake_evidence_matcher import FakeEvidenceMatcher
from careerops.adapters.groq_evidence_matcher import GroqEvidenceMatcher
from careerops.core.config import Settings
from careerops.domain.analysis_runs import (
    FAKE_ANALYSIS_MODEL_NAME,
    EvidenceMatcherOutput,
    matcher_prompt_version_from_pipeline,
)
from careerops.domain.errors import EvidenceMatcherError, EvidenceMatcherFailureReason
from careerops.domain.evidence_matching import (
    MATCHER_PROMPT_VERSION_V4,
    EvidenceMatcherInput,
)
from careerops.services.analysis_run_execution import EvidenceMatcher

LIVE_MATCHER_ENV = "CAREEROPS_RUN_REAL_MATCHER_WORKER"
GROQ_EVIDENCE_MATCHER_MODEL = "openai/gpt-oss-20b"
GROQ_EVIDENCE_MATCHER_MAX_OUTPUT_TOKENS = 800


class UnavailableEvidenceMatcher:
    def __init__(self, model_name: str, reason: EvidenceMatcherFailureReason) -> None:
        self._model_name = model_name
        self._reason = reason

    @property
    def model_name(self) -> str:
        return self._model_name

    async def match(
        self,
        matcher_input: EvidenceMatcherInput,
    ) -> EvidenceMatcherOutput:
        raise EvidenceMatcherError(self._reason)


class ConfiguredEvidenceMatcherResolver:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def resolve(self, model_name: str, prompt_version: str) -> EvidenceMatcher:
        if model_name == FAKE_ANALYSIS_MODEL_NAME:
            return FakeEvidenceMatcher()
        if (
            model_name != GROQ_EVIDENCE_MATCHER_MODEL
            or prompt_version != MATCHER_PROMPT_VERSION_V4
        ):
            return UnavailableEvidenceMatcher(
                model_name,
                EvidenceMatcherFailureReason.MISCONFIGURED,
            )
        if os.environ.get(LIVE_MATCHER_ENV) != "1":
            return UnavailableEvidenceMatcher(
                model_name,
                EvidenceMatcherFailureReason.DISABLED,
            )
        if self._settings.llm_api_key is None:
            return UnavailableEvidenceMatcher(
                model_name,
                EvidenceMatcherFailureReason.MISCONFIGURED,
            )
        return GroqEvidenceMatcher(
            api_key=self._settings.llm_api_key.get_secret_value(),
            model=GROQ_EVIDENCE_MATCHER_MODEL,
            base_url=self._settings.llm_base_url,
            timeout_seconds=self._settings.llm_timeout_seconds,
            max_attempts=1,
            retry_base_delay_seconds=self._settings.llm_retry_base_delay_seconds,
            max_output_tokens=GROQ_EVIDENCE_MATCHER_MAX_OUTPUT_TOKENS,
        )

    def resolve_pipeline(self, model_name: str, pipeline_version: str) -> EvidenceMatcher:
        try:
            prompt_version = matcher_prompt_version_from_pipeline(pipeline_version)
        except ValueError:
            return UnavailableEvidenceMatcher(
                model_name,
                EvidenceMatcherFailureReason.MISCONFIGURED,
            )
        return self.resolve(model_name, prompt_version)


def configured_evidence_matcher_model(settings: Settings) -> str:
    if settings.evidence_matcher_provider == "fake":
        return FAKE_ANALYSIS_MODEL_NAME
    return GROQ_EVIDENCE_MATCHER_MODEL
