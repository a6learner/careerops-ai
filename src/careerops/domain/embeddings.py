import json
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from careerops.domain.experiences import ExperienceRecord

EMBEDDING_DIMENSIONS = 1536
EMBEDDING_INPUT_VERSION = "experience-embedding-input-v1"
FAKE_EMBEDDING_MODEL_NAME = "local-fake-embedding-1536"
FAKE_QUERY_INPUT_VERSION = "local-fake-search-query-v1"
GEMINI_EMBEDDING_MODEL_NAME = "gemini-embedding-2"
GEMINI_QUERY_INPUT_VERSION = "gemini-embedding-2-search-query-v1"
GEMINI_DOCUMENT_INPUT_VERSION = "gemini-embedding-2-search-document-v1"
HYBRID_RETRIEVAL_VERSION = "weighted-rrf-v1"


@dataclass(frozen=True)
class EmbeddingSpace:
    model_name: str
    dimensions: int
    query_input_version: str
    document_input_version: str


FAKE_EMBEDDING_SPACE = EmbeddingSpace(
    model_name=FAKE_EMBEDDING_MODEL_NAME,
    dimensions=EMBEDDING_DIMENSIONS,
    query_input_version=FAKE_QUERY_INPUT_VERSION,
    document_input_version=EMBEDDING_INPUT_VERSION,
)
GEMINI_EMBEDDING_SPACE = EmbeddingSpace(
    model_name=GEMINI_EMBEDDING_MODEL_NAME,
    dimensions=EMBEDDING_DIMENSIONS,
    query_input_version=GEMINI_QUERY_INPUT_VERSION,
    document_input_version=GEMINI_DOCUMENT_INPUT_VERSION,
)


def embedding_space_for_provider(provider_name: str) -> EmbeddingSpace:
    if provider_name == "fake":
        return FAKE_EMBEDDING_SPACE
    if provider_name == "gemini":
        return GEMINI_EMBEDDING_SPACE
    raise ValueError(f"Unsupported embedding provider: {provider_name}")


def analysis_pipeline_version(space: EmbeddingSpace) -> str:
    return ":".join(
        (
            "match-v2",
            HYBRID_RETRIEVAL_VERSION,
            space.model_name,
            space.query_input_version,
            space.document_input_version,
        )
    )


def embedding_space_for_analysis_pipeline(version: str) -> EmbeddingSpace:
    for space in (FAKE_EMBEDDING_SPACE, GEMINI_EMBEDDING_SPACE):
        if version == analysis_pipeline_version(space):
            return space
    raise ValueError(f"Unsupported Analysis pipeline version: {version}")


class EmbeddingRunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SUPERSEDED = "superseded"


class EmbeddingRunErrorCode(StrEnum):
    PROVIDER_FAILED = "EMBEDDING_PROVIDER_FAILED"
    PROVIDER_DISABLED = "EMBEDDING_PROVIDER_DISABLED"
    PROVIDER_MISCONFIGURED = "EMBEDDING_PROVIDER_MISCONFIGURED"
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


def render_document_embedding_input(
    experience: ExperienceRecord,
    input_version: str,
) -> str:
    payload = {
        "description": experience.description,
        "kind": experience.kind.value,
        "outcome": experience.outcome,
        "skills": list(experience.skills),
        "title": experience.title,
    }
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if input_version == EMBEDDING_INPUT_VERSION:
        return text
    if input_version == GEMINI_DOCUMENT_INPUT_VERSION:
        without_title = {
            "description": experience.description,
            "kind": experience.kind.value,
            "outcome": experience.outcome,
            "skills": list(experience.skills),
        }
        document = json.dumps(
            without_title,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return f"title: {experience.title} | text: {document}"
    raise ValueError(f"Unsupported document embedding input version: {input_version}")


def render_query_embedding_input(requirement_text: str, input_version: str) -> str:
    if input_version in {FAKE_QUERY_INPUT_VERSION, GEMINI_QUERY_INPUT_VERSION}:
        return f"task: search result | query: {requirement_text}"
    raise ValueError(f"Unsupported query embedding input version: {input_version}")
