"""BGE embeddings client for the workshop.

Wraps the OpenAI-compatible API exposed by Scaleway Managed Inference
(BGE Multilingual Gemma2 on L4) to embed text for pgvector storage and
similarity search.
"""

from __future__ import annotations

from typing import Any


class EmbeddingsClient:
    """Client for generating text embeddings via an OpenAI-compatible API.

    Args:
        client: An OpenAI-compatible client instance (e.g., openai.OpenAI).
        model: The model identifier to use for embeddings.
        dimensions: Optional truncation. BGE Gemma2 is a Matryoshka model,
            so the first N dims are a valid lower-dim embedding. 768 matches
            the showcase 3 reference and fits under pgvector's 2000-dim
            index cap.
    """

    def __init__(self, client: Any, model: str, dimensions: int | None = None) -> None:
        self._client = client
        self._model = model
        self._dimensions = dimensions

    def _truncate(self, vec: list[float]) -> list[float]:
        if self._dimensions is None:
            return vec
        return vec[: self._dimensions]

    def embed(self, text: str) -> list[float]:
        """Embed a single text string.

        Args:
            text: The text to embed.

        Returns:
            A list of floats representing the embedding vector.
        """
        response = self._client.embeddings.create(
            input=[text],
            model=self._model,
        )
        return self._truncate(response.data[0].embedding)

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts in a single API call.

        Args:
            texts: List of text strings to embed.

        Returns:
            List of embedding vectors, one per input text.
        """
        if not texts:
            return []

        response = self._client.embeddings.create(
            input=texts,
            model=self._model,
        )
        sorted_data = sorted(response.data, key=lambda x: x.index)
        return [self._truncate(item.embedding) for item in sorted_data]
