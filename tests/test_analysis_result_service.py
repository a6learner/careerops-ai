from uuid import UUID, uuid4

import pytest

from careerops.domain.evidence_matching import EvidenceVerdict, ValidatedEvidenceMatch
from careerops.services.analysis_results import AnalysisResultService


class RecordingAnalysisResultStore:
    def __init__(self, *, completes: bool = True) -> None:
        self.completes = completes
        self.validation_failure_count: int | None = None
        self.committed = False

    async def complete_analysis_run(
        self,
        analysis_run_id: UUID,
        matches: tuple[ValidatedEvidenceMatch, ...],
        validation_failure_count: int,
    ) -> bool:
        self.validation_failure_count = validation_failure_count
        return self.completes

    async def commit(self) -> None:
        self.committed = True


@pytest.mark.asyncio
async def test_completion_counts_downgraded_matches_and_commits_once() -> None:
    store = RecordingAnalysisResultStore()
    matches = (
        make_match(validation_failed=False),
        make_match(validation_failed=True),
        make_match(validation_failed=True),
    )

    completed = await AnalysisResultService(store).complete(uuid4(), matches)

    assert completed
    assert store.validation_failure_count == 2
    assert store.committed


@pytest.mark.asyncio
async def test_duplicate_worker_completion_does_not_commit() -> None:
    store = RecordingAnalysisResultStore(completes=False)

    completed = await AnalysisResultService(store).complete(uuid4(), ())

    assert not completed
    assert not store.committed


def make_match(*, validation_failed: bool) -> ValidatedEvidenceMatch:
    return ValidatedEvidenceMatch(
        requirement_id=uuid4(),
        verdict=EvidenceVerdict.INSUFFICIENT_EVIDENCE,
        experience_id=None,
        experience_version=None,
        quote=None,
        quote_valid=False,
        confidence=None,
        validation_failed=validation_failed,
    )
