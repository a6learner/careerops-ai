import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from careerops.adapters.groq_evidence_matcher import GroqEvidenceMatcher
from careerops.evaluation.evidence_matcher import (
    load_matcher_dataset,
    load_matcher_review_manifest,
)
from careerops.evaluation.evidence_retrieval_v2 import RetrievalSplit, ReviewStatus, load_corpus
from careerops.evaluation.run_real_evidence_matcher import create_matcher, run

CORPUS_PATH = Path("evals/evidence_retrieval_v2/experiences.json")
DEVELOPMENT_PATH = Path("evals/evidence_matcher_v1/development_cases.json")
MANIFEST_PATH = Path("evals/evidence_matcher_v1/review_manifest.json")
RUN_MANIFEST_PATH = Path(
    "evals/evidence_matcher_v1/prompt_v4_selected_development_manifest.json"
)
PARTIAL_REAL_REPORT_PATH = Path(
    "docs/metrics/2026-10-04-groq-evidence-matcher-development.json"
)


def approved_manifest_path(tmp_path: Path) -> Path:
    manifest = load_matcher_review_manifest(MANIFEST_PATH).model_copy(
        update={
            "status": ReviewStatus.APPROVED_FROZEN,
            "reviewer": "unit test",
            "reviewed_at": datetime(2026, 10, 4, tzinfo=UTC),
        }
    )
    path = tmp_path / "approved-manifest.json"
    path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    return path


async def no_sleep(_: float) -> None:
    return None


def make_matcher(
    handler: httpx.MockTransport,
    *,
    max_attempts: int = 1,
) -> GroqEvidenceMatcher:
    return GroqEvidenceMatcher(
        api_key="test-key",
        model="openai/gpt-oss-20b",
        base_url="https://api.groq.test/openai/v1",
        timeout_seconds=1.0,
        max_attempts=max_attempts,
        retry_base_delay_seconds=0.0,
        max_output_tokens=800,
        transport=handler,
        sleep=no_sleep,
    )


def gap_response(request: httpx.Request) -> httpx.Response:
    request_body = json.loads(request.content)
    matcher_input = json.loads(request_body["messages"][1]["content"])
    return httpx.Response(
        200,
        request=request,
        json={
            "model": "openai/gpt-oss-20b",
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "schema_version": "evidence-matcher-schema-v1",
                                "matches": [
                                    {
                                        "requirement_id": requirement["requirement_id"],
                                        "verdict": "missing",
                                        "evidence": None,
                                        "confidence": 0.8,
                                    }
                                    for requirement in matcher_input["requirements"]
                                ],
                            }
                        )
                    }
                }
            ],
            "usage": {"prompt_tokens": 100, "completion_tokens": 20},
        },
    )


def test_real_runner_requires_invocation_local_opt_in(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("CAREEROPS_RUN_MATCHER_EVAL", raising=False)
    monkeypatch.setenv("CAREEROPS_LLM_API_KEY", "test-key")

    with pytest.raises(RuntimeError, match="CAREEROPS_RUN_MATCHER_EVAL=1"):
        create_matcher()


def test_real_runner_requires_api_key_after_opt_in(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CAREEROPS_RUN_MATCHER_EVAL", "1")
    monkeypatch.delenv("CAREEROPS_LLM_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="CAREEROPS_LLM_API_KEY"):
        create_matcher()


@pytest.mark.asyncio
async def test_real_runner_is_bounded_and_writes_development_report(tmp_path: Path) -> None:
    matcher = make_matcher(httpx.MockTransport(gap_response))
    output_path = tmp_path / "real-development.json"
    manifest_path = approved_manifest_path(tmp_path)

    report = await run(
        experiences_path=CORPUS_PATH,
        cases_path=DEVELOPMENT_PATH,
        review_manifest_path=manifest_path,
        run_manifest_path=RUN_MANIFEST_PATH,
        output_path=output_path,
        git_revision="test-revision",
        matcher=matcher,
    )

    assert report.provider == "groq"
    assert report.provider_request_attempt_count == 12
    assert report.provider_request_budget == 12
    assert report.summary.case_count == 12
    assert report.summary.total_input_tokens == 1_200
    assert output_path.exists()


@pytest.mark.asyncio
async def test_real_runner_recovers_only_failed_cases_into_new_report(tmp_path: Path) -> None:
    calls = 0
    manifest_path = approved_manifest_path(tmp_path)

    def partial_response(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls > 6:
            return httpx.Response(429, request=request)
        return gap_response(request)

    prior_path = tmp_path / "partial.json"
    prior = await run(
        experiences_path=CORPUS_PATH,
        cases_path=DEVELOPMENT_PATH,
        review_manifest_path=manifest_path,
        run_manifest_path=RUN_MANIFEST_PATH,
        output_path=prior_path,
        git_revision="test-revision",
        matcher=make_matcher(httpx.MockTransport(partial_response)),
    )
    assert prior.summary.completed_case_count == 6

    recovery_matcher = make_matcher(httpx.MockTransport(gap_response))
    recovery_path = tmp_path / "recovered.json"
    recovered = await run(
        experiences_path=CORPUS_PATH,
        cases_path=DEVELOPMENT_PATH,
        review_manifest_path=manifest_path,
        run_manifest_path=RUN_MANIFEST_PATH,
        output_path=recovery_path,
        git_revision="test-revision",
        matcher=recovery_matcher,
        prior_report_path=prior_path,
    )

    assert recovery_matcher.request_attempt_count == 6
    assert recovered.provider_request_attempt_count == 6
    assert recovered.provider_request_budget == 6
    assert recovered.cumulative_provider_request_attempt_count == 18
    assert recovered.resumed_from_sha256 is not None
    assert recovered.summary.completed_case_count == 12
    assert recovered.cases[:6] == prior.cases[:6]
    assert recovery_path.exists()


@pytest.mark.asyncio
async def test_checked_in_v1_partial_report_is_rejected_after_dataset_relabel(
    tmp_path: Path,
) -> None:
    matcher = make_matcher(httpx.MockTransport(gap_response))
    manifest_path = approved_manifest_path(tmp_path)

    with pytest.raises(ValueError, match="Prior matcher report does not match"):
        await run(
            experiences_path=CORPUS_PATH,
            cases_path=DEVELOPMENT_PATH,
            review_manifest_path=manifest_path,
            run_manifest_path=RUN_MANIFEST_PATH,
            output_path=tmp_path / "checked-in-recovery.json",
            git_revision="test-revision",
            matcher=matcher,
            prior_report_path=PARTIAL_REAL_REPORT_PATH,
        )

    assert matcher.request_attempt_count == 0


@pytest.mark.asyncio
async def test_real_runner_rejects_holdout_without_provider_call(tmp_path: Path) -> None:
    matcher = make_matcher(httpx.MockTransport(gap_response))
    corpus, _ = load_corpus(CORPUS_PATH)
    development, _ = load_matcher_dataset(DEVELOPMENT_PATH, corpus)
    toy_holdout = development.model_copy(update={"split": RetrievalSplit.HOLDOUT})
    toy_holdout_path = tmp_path / "toy-holdout.json"
    toy_holdout_path.write_text(toy_holdout.model_dump_json(indent=2), encoding="utf-8")

    with pytest.raises(RuntimeError, match="holdout is sealed"):
        await run(
            experiences_path=CORPUS_PATH,
            cases_path=toy_holdout_path,
            review_manifest_path=MANIFEST_PATH,
            run_manifest_path=RUN_MANIFEST_PATH,
            output_path=tmp_path / "holdout.json",
            git_revision="test-revision",
            matcher=matcher,
        )

    assert matcher.request_attempt_count == 0


@pytest.mark.asyncio
async def test_real_runner_rejects_changed_frozen_prompt_manifest_without_call(
    tmp_path: Path,
) -> None:
    matcher = make_matcher(httpx.MockTransport(gap_response))
    manifest = json.loads(RUN_MANIFEST_PATH.read_text(encoding="utf-8"))
    manifest["prompt_sha256"] = "0" * 64
    changed_manifest_path = tmp_path / "changed-run-manifest.json"
    changed_manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="frozen configuration"):
        await run(
            experiences_path=CORPUS_PATH,
            cases_path=DEVELOPMENT_PATH,
            review_manifest_path=MANIFEST_PATH,
            run_manifest_path=changed_manifest_path,
            output_path=tmp_path / "report.json",
            git_revision="test-revision",
            matcher=matcher,
        )

    assert matcher.request_attempt_count == 0


@pytest.mark.asyncio
async def test_real_runner_rejects_attempts_over_budget_without_report(tmp_path: Path) -> None:
    def unavailable(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, request=request)

    matcher = make_matcher(httpx.MockTransport(unavailable), max_attempts=2)
    output_path = tmp_path / "over-budget.json"
    manifest_path = approved_manifest_path(tmp_path)

    with pytest.raises(RuntimeError, match="exceeded its provider request budget"):
        await run(
            experiences_path=CORPUS_PATH,
            cases_path=DEVELOPMENT_PATH,
            review_manifest_path=manifest_path,
            run_manifest_path=RUN_MANIFEST_PATH,
            output_path=output_path,
            git_revision="test-revision",
            matcher=matcher,
        )

    assert matcher.request_attempt_count == 24
    assert not output_path.exists()
