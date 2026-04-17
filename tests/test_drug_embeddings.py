"""Tests for src/drug_embeddings.py - BGE embeddings client."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_client(embedding_dim: int = 3584):
    """Create a mock OpenAI-compatible client for embeddings."""
    client = MagicMock()

    def _create_embeddings(input, model):
        data = []
        texts = input if isinstance(input, list) else [input]
        for i, _ in enumerate(texts):
            item = MagicMock()
            item.embedding = [0.1] * embedding_dim
            item.index = i
            data.append(item)
        response = MagicMock()
        response.data = data
        return response

    client.embeddings.create.side_effect = _create_embeddings
    return client


# ---------------------------------------------------------------------------
# Tests: EmbeddingsClient.embed
# ---------------------------------------------------------------------------


class TestEmbed:
    """Test EmbeddingsClient.embed() returns correct dimension vector."""

    def test_returns_correct_dimension(self) -> None:
        """embed() returns a vector with the expected number of dimensions."""
        from src.drug_embeddings import EmbeddingsClient

        client = _make_mock_client(embedding_dim=3584)
        ec = EmbeddingsClient(client=client, model="bge-multilingual-gemma2")

        result = ec.embed("test text")

        assert isinstance(result, list)
        assert len(result) == 3584

    def test_calls_api_with_correct_params(self) -> None:
        """embed() calls the API with the correct model and input."""
        from src.drug_embeddings import EmbeddingsClient

        client = _make_mock_client()
        ec = EmbeddingsClient(client=client, model="bge-multilingual-gemma2")

        ec.embed("drug interaction warfarin")

        client.embeddings.create.assert_called_once()
        call_kwargs = client.embeddings.create.call_args
        assert call_kwargs.kwargs["model"] == "bge-multilingual-gemma2"


# ---------------------------------------------------------------------------
# Tests: EmbeddingsClient.embed_batch
# ---------------------------------------------------------------------------


class TestEmbedBatch:
    """Test EmbeddingsClient.embed_batch() preserves order and handles edge cases."""

    def test_preserves_order(self) -> None:
        """embed_batch() returns embeddings in the same order as input texts."""
        from src.drug_embeddings import EmbeddingsClient

        client = _make_mock_client()
        ec = EmbeddingsClient(client=client, model="bge-multilingual-gemma2")

        texts = ["text1", "text2", "text3"]
        results = ec.embed_batch(texts)

        assert len(results) == 3
        for r in results:
            assert len(r) == 3584

    def test_handles_empty_input(self) -> None:
        """embed_batch() returns empty list for empty input."""
        from src.drug_embeddings import EmbeddingsClient

        client = _make_mock_client()
        ec = EmbeddingsClient(client=client, model="bge-multilingual-gemma2")

        results = ec.embed_batch([])

        assert results == []
        client.embeddings.create.assert_not_called()

    def test_single_text(self) -> None:
        """embed_batch() handles a single text input correctly."""
        from src.drug_embeddings import EmbeddingsClient

        client = _make_mock_client()
        ec = EmbeddingsClient(client=client, model="bge-multilingual-gemma2")

        results = ec.embed_batch(["single text"])

        assert len(results) == 1
        assert len(results[0]) == 3584
