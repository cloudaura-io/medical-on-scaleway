"""BGE embeddings client for the Drug Interactions showcase.

Wraps the OpenAI-compatible API exposed by Scaleway Managed Inference
(BGE Multilingual Gemma2 on L4) to embed text for pgvector storage and
similarity search.

Adapted from workshop/src/embeddings.py.
"""

from __future__ import annotations

from typing import Any


class EmbeddingsClient:
    """Client for generating text embeddings via an OpenAI-compatible API.

    Args:
        client: An OpenAI-compatible client instance (e.g., openai.OpenAI).
        model: The model identifier to use for embeddings.
        dimensions: Optional output dimension count. If the model supports
            native dimension control (e.g., Qwen3), the server truncates
            server-side. Otherwise omitted.
    """

    def __init__(self, client: Any, model: str, dimensions: int | None = None) -> None:
        self._client = client
        self._model = model
        self._dimensions = dimensions

    def _extra_kwargs(self) -> dict:
        if self._dimensions is not None:
            return {"dimensions": self._dimensions}
        return {}

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
            **self._extra_kwargs(),
        )
        return response.data[0].embedding

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
            **self._extra_kwargs(),
        )
        # Sort by index to ensure correct ordering
        sorted_data = sorted(response.data, key=lambda x: x.index)
        return [item.embedding for item in sorted_data]
