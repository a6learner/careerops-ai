from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from careerops.domain.experiences import ExperienceRecord

EMBEDDING_DIMENSIONS = 1536
EMBEDDING_INPUT_VERSION = "experience-embedding-input-v1"
FAKE_EMBEDDING_MODEL_NAME = "local-fake-embedding-1536"


class EmbeddingRunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SUPERSEDED = "superseded"


class EmbeddingRunErrorCode(StrEnum):
    PROVIDER_FAILED = "EMBEDDING_PROVIDER_FAILED"
    OUTPUT_INVALID = "EMBEDDING_OUTPUT_INVALID"


@dataclass(frozen=True)
class EmbeddingOutput:
    model_name: str
    vector: tuple[float, ...]


@dataclass(frozen=True)
class EmbeddingRunWorkItem:
    id: UUID
    attempt: int
    experience: ExperienceRecord
    model_name: str
    input_version: str
