import hashlib

from careerops.domain.embeddings import (
    EMBEDDING_DIMENSIONS,
    FAKE_EMBEDDING_MODEL_NAME,
    EmbeddingOutput,
)


class FakeEmbeddingProvider:
    @property
    def model_name(self) -> str:
        return FAKE_EMBEDDING_MODEL_NAME

    async def embed(self, input_text: str) -> EmbeddingOutput:
        values: list[float] = []
        encoded = input_text.encode("utf-8")
        block = 0
        while len(values) < EMBEDDING_DIMENSIONS:
            digest = hashlib.sha256(encoded + block.to_bytes(4, "big")).digest()
            values.extend((byte - 127.5) / 127.5 for byte in digest)
            block += 1
        return EmbeddingOutput(
            model_name=self.model_name,
            vector=tuple(values[:EMBEDDING_DIMENSIONS]),
        )
