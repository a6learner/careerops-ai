import argparse
import asyncio
import json
import os
from hashlib import sha256
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from careerops.adapters.evidence_matcher_schema import evidence_matcher_instructions
from careerops.adapters.groq_evidence_matcher import (
    GroqEvidenceMatcher,
    groq_matcher_response_json_schema,
)
from careerops.domain.evidence_matching import (
    MATCHER_PROMPT_VERSION,
    MATCHER_SCHEMA_VERSION,
)
from careerops.evaluation.evidence_matcher import load_matcher_dataset
from careerops.evaluation.evidence_retrieval_v2 import RetrievalSplit, load_corpus
from careerops.evaluation.run_evidence_matcher import MatcherEvalReport, run_development

GROQ_MATCHER_MODEL = "openai/gpt-oss-20b"
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
MATCHER_DEVELOPMENT_REQUEST_BUDGET = 12
MATCHER_MAX_OUTPUT_TOKENS = 800
MATCHER_MINIMUM_REQUEST_INTERVAL_SECONDS = 11.0
MATCHER_DEVELOPMENT_GATE_POLICY_VERSION = "evidence-matcher-development-gates-v4"


class MatcherDevelopmentRunManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal[1]
    status: Literal["approved_frozen"]
    authorized_by: str
    authorized_at: str
    corpus_sha256: str
    development_cases_sha256: str
    prompt_version: str
    prompt_sha256: str
    schema_version: str
    response_schema_sha256: str
    acceptance_policy_version: str
    provider: Literal["groq"]
    model: str
    request_budget: int
    max_attempts_per_case: int
    minimum_request_interval_seconds: float
    max_output_tokens: int
    reasoning_effort: Literal["low"]
    temperature: float


class MatcherEvaluationSecrets(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    groq_api_key: SecretStr | None = Field(
        default=None,
        validation_alias="CAREEROPS_LLM_API_KEY",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run one bounded Groq Evidence Matcher development evaluation."
    )
    parser.add_argument("--experiences", type=Path, required=True)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--review-manifest", type=Path, required=True)
    parser.add_argument("--run-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--git-revision", required=True)
    parser.add_argument("--resume-from", type=Path)
    return parser.parse_args()


def create_matcher() -> GroqEvidenceMatcher:
    if os.environ.get("CAREEROPS_RUN_MATCHER_EVAL") != "1":
        raise RuntimeError(
            "Set CAREEROPS_RUN_MATCHER_EVAL=1 for this invocation to authorize the Groq run."
        )
    api_key = MatcherEvaluationSecrets().groq_api_key
    if api_key is None or api_key.get_secret_value().strip() == "":
        raise RuntimeError("CAREEROPS_LLM_API_KEY is required for the authorized Groq run.")
    return GroqEvidenceMatcher(
        api_key=api_key.get_secret_value(),
        model=GROQ_MATCHER_MODEL,
        base_url=GROQ_BASE_URL,
        timeout_seconds=30.0,
        max_attempts=1,
        retry_base_delay_seconds=0.0,
        max_output_tokens=MATCHER_MAX_OUTPUT_TOKENS,
        minimum_request_interval_seconds=MATCHER_MINIMUM_REQUEST_INTERVAL_SECONDS,
    )


async def run(
    *,
    experiences_path: Path,
    cases_path: Path,
    review_manifest_path: Path,
    run_manifest_path: Path,
    output_path: Path,
    git_revision: str,
    matcher: GroqEvidenceMatcher,
    prior_report_path: Path | None = None,
) -> MatcherEvalReport:
    corpus, _ = load_corpus(experiences_path)
    dataset, _ = load_matcher_dataset(cases_path, corpus)
    if dataset.split is not RetrievalSplit.DEVELOPMENT:
        raise RuntimeError("Matcher holdout is sealed from the development runner.")
    validate_development_run_manifest(
        run_manifest_path,
        experiences_path=experiences_path,
        cases_path=cases_path,
    )
    prior_report: MatcherEvalReport | None = None
    resumed_from_sha256: str | None = None
    request_budget = MATCHER_DEVELOPMENT_REQUEST_BUDGET
    if prior_report_path is not None:
        prior_content = prior_report_path.read_bytes()
        prior_report = MatcherEvalReport.model_validate_json(prior_content)
        resumed_from_sha256 = sha256(prior_content).hexdigest()
        request_budget = sum(case.error_type is not None for case in prior_report.cases)
    return await run_development(
        experiences_path=experiences_path,
        cases_path=cases_path,
        review_manifest_path=review_manifest_path,
        output_path=output_path,
        git_revision=git_revision,
        provider_name="groq",
        matcher=matcher,
        request_attempt_count=lambda: matcher.request_attempt_count,
        provider_request_budget=request_budget,
        prior_report=prior_report,
        resumed_from_sha256=resumed_from_sha256,
        limitations=[
            "Synthetic development labels do not establish holdout or production accuracy.",
            "One project author reviewed the labels; inter-annotator agreement is not measured.",
            "Provider behavior may change even when the model identifier is unchanged.",
            "Candidate lists are frozen matcher inputs; retrieval quality is reported separately.",
            "A fresh run makes at most 12 provider attempts; recovery calls only prior "
            "failed cases and never retries a case within one invocation.",
            "The matcher holdout remains sealed and receives zero provider calls.",
            "Latency excludes API, queue, database, and worker time.",
        ],
    )


def main() -> None:
    args = parse_args()
    matcher = create_matcher()
    report = asyncio.run(
        run(
            experiences_path=args.experiences,
            cases_path=args.cases,
            review_manifest_path=args.review_manifest,
            run_manifest_path=args.run_manifest,
            output_path=args.output,
            git_revision=args.git_revision,
            matcher=matcher,
            prior_report_path=args.resume_from,
        )
    )
    print(report.summary.model_dump_json(indent=2))


def validate_development_run_manifest(
    path: Path,
    *,
    experiences_path: Path,
    cases_path: Path,
) -> MatcherDevelopmentRunManifest:
    manifest = MatcherDevelopmentRunManifest.model_validate_json(path.read_bytes())
    prompt_hash = sha256(
        evidence_matcher_instructions(MATCHER_PROMPT_VERSION).encode("utf-8")
    ).hexdigest()
    schema_hash = sha256(
        json.dumps(
            groq_matcher_response_json_schema(),
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    expected = {
        "corpus_sha256": sha256(experiences_path.read_bytes()).hexdigest(),
        "development_cases_sha256": sha256(cases_path.read_bytes()).hexdigest(),
        "prompt_version": MATCHER_PROMPT_VERSION,
        "prompt_sha256": prompt_hash,
        "schema_version": MATCHER_SCHEMA_VERSION,
        "response_schema_sha256": schema_hash,
        "acceptance_policy_version": MATCHER_DEVELOPMENT_GATE_POLICY_VERSION,
        "model": GROQ_MATCHER_MODEL,
        "request_budget": MATCHER_DEVELOPMENT_REQUEST_BUDGET,
        "max_attempts_per_case": 1,
        "minimum_request_interval_seconds": MATCHER_MINIMUM_REQUEST_INTERVAL_SECONDS,
        "max_output_tokens": MATCHER_MAX_OUTPUT_TOKENS,
        "reasoning_effort": "low",
        "temperature": 0.0,
    }
    actual = manifest.model_dump(include=set(expected))
    if actual != expected:
        raise ValueError("Development run manifest does not match the frozen configuration.")
    if not manifest.authorized_by.strip() or not manifest.authorized_at.strip():
        raise ValueError("Development run manifest requires authorization provenance.")
    return manifest


if __name__ == "__main__":
    main()
