"""Tests for workshop/src/embeddings.py - BGE embeddings client."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_openai_client(embedding_dim: int = 3584) -> MagicMock:
    """Create a mock OpenAI client that returns fake embeddings."""
    client = MagicMock()

    def _create_embeddings(**kwargs):
        inputs = kwargs.get("input", [])
        if isinstance(inputs, str):
            inputs = [inputs]

        mock_response = MagicMock()
        mock_data = []
        for i, _ in enumerate(inputs):
            item = MagicMock()
            item.embedding = [0.1 * (i + 1)] * embedding_dim
            item.index = i
            mock_data.append(item)
        mock_response.data = mock_data
        return mock_response

    client.embeddings.create = MagicMock(side_effect=_create_embeddings)
    return client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestEmbedSingle:
    """Test embedding a single text."""

    def test_returns_list_of_floats(self) -> None:
        """embed() returns a list of floats of the expected dimension."""
        from workshop.src.embeddings import EmbeddingsClient

        mock_client = _mock_openai_client()
        ec = EmbeddingsClient(client=mock_client, model="bge-multilingual-gemma2")

        result = ec.embed("test text")

        assert isinstance(result, list)
        assert len(result) == 3584
        assert all(isinstance(x, float) for x in result)

    def test_calls_openai_create(self) -> None:
        """embed() calls the OpenAI embeddings.create endpoint."""
        from workshop.src.embeddings import EmbeddingsClient

        mock_client = _mock_openai_client()
        ec = EmbeddingsClient(client=mock_client, model="bge-multilingual-gemma2")

        ec.embed("hello world")

        mock_client.embeddings.create.assert_called_once()
        call_kwargs = mock_client.embeddings.create.call_args[1]
        assert call_kwargs["model"] == "bge-multilingual-gemma2"


class TestEmbedBatch:
    """Test batch embedding of multiple texts."""

    def test_returns_list_of_embeddings(self) -> None:
        """embed_batch() returns one embedding per input text."""
        from workshop.src.embeddings import EmbeddingsClient

        mock_client = _mock_openai_client()
        ec = EmbeddingsClient(client=mock_client, model="bge-multilingual-gemma2")

        texts = ["text one", "text two", "text three"]
        results = ec.embed_batch(texts)

        assert len(results) == 3
        for emb in results:
            assert len(emb) == 3584

    def test_empty_input_returns_empty_list(self) -> None:
        """embed_batch([]) returns an empty list without API calls."""
        from workshop.src.embeddings import EmbeddingsClient

        mock_client = _mock_openai_client()
        ec = EmbeddingsClient(client=mock_client, model="bge-multilingual-gemma2")

        results = ec.embed_batch([])

        assert results == []
