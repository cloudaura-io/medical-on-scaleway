"""Tests for workshop/src/rag.py - pgvector helpers."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_connection() -> MagicMock:
    """Create a mock psycopg connection with cursor context manager."""
    conn = MagicMock()
    cursor = MagicMock()

    # Make cursor work as a context manager
    conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    return conn, cursor


def _sample_chunks() -> list[dict]:
    """Sample chunks for testing inserts."""
    return [
        {
            "section_type": "drug_interactions",
            "text": "Warfarin interacts with aspirin and NSAIDs.",
            "drug_name": "WARFARIN SODIUM",
            "generic_name": "WARFARIN SODIUM",
            "brand_name": "WARFARIN SODIUM",
            "set_id": "e98a2d84-c192-4d2a-b202-61a81b0c7dda",
            "application_number": "ANDA076807",
            "manufacturer_name": "Taro Pharmaceuticals",
            "source_url": "https://api.fda.gov/drug/label.json?search=openfda.set_id:e98a2d84",
            "embedding": [0.1] * 3584,
        },
        {
            "section_type": "pregnancy",
            "text": "Warfarin is contraindicated in pregnancy.",
            "drug_name": "WARFARIN SODIUM",
            "generic_name": "WARFARIN SODIUM",
            "brand_name": "WARFARIN SODIUM",
            "set_id": "e98a2d84-c192-4d2a-b202-61a81b0c7dda",
            "application_number": "ANDA076807",
            "manufacturer_name": "Taro Pharmaceuticals",
            "source_url": "https://api.fda.gov/drug/label.json?search=openfda.set_id:e98a2d84",
            "embedding": [0.2] * 3584,
        },
    ]


# ---------------------------------------------------------------------------
# Tests: insert_chunks
# ---------------------------------------------------------------------------


class TestInsertChunks:
    """Test bulk chunk insertion."""

    def test_inserts_all_chunks(self) -> None:
        """insert_chunks executes one INSERT per chunk."""
        from workshop.src.rag import insert_chunks

        conn, cursor = _mock_connection()
        chunks = _sample_chunks()

        insert_chunks(conn, chunks)

        assert cursor.execute.call_count == len(chunks)

    def test_commits_after_insert(self) -> None:
        """insert_chunks commits the transaction."""
        from workshop.src.rag import insert_chunks

        conn, cursor = _mock_connection()
        chunks = _sample_chunks()

        insert_chunks(conn, chunks)

        conn.commit.assert_called_once()


# ---------------------------------------------------------------------------
# Tests: similarity_search
# ---------------------------------------------------------------------------


class TestSimilaritySearch:
    """Test vector similarity search."""

    def test_returns_results(self) -> None:
        """similarity_search returns rows from the cursor."""
        from workshop.src.rag import similarity_search

        conn, cursor = _mock_connection()
        cursor.fetchall.return_value = [
            {
                "drug_name": "WARFARIN SODIUM",
                "section_type": "drug_interactions",
                "text": "Warfarin interacts with aspirin.",
                "set_id": "e98a2d84",
                "distance": 0.15,
            }
        ]

        query_embedding = [0.1] * 3584
        results = similarity_search(conn, query_embedding, k=5)

        assert len(results) == 1
        assert results[0]["drug_name"] == "WARFARIN SODIUM"

    def test_respects_k_parameter(self) -> None:
        """similarity_search limits results to k."""
        from workshop.src.rag import similarity_search

        conn, cursor = _mock_connection()
        cursor.fetchall.return_value = []

        query_embedding = [0.1] * 3584
        similarity_search(conn, query_embedding, k=3)

        # Verify the SQL contains a LIMIT clause
        execute_call = cursor.execute.call_args
        sql = execute_call[0][0]
        assert "LIMIT" in sql.upper() or "limit" in sql

    def test_filter_by_drug_name(self) -> None:
        """similarity_search supports filtering by drug_name."""
        from workshop.src.rag import similarity_search

        conn, cursor = _mock_connection()
        cursor.fetchall.return_value = []

        query_embedding = [0.1] * 3584
        similarity_search(conn, query_embedding, k=5, filters={"drug_name": "warfarin"})

        execute_call = cursor.execute.call_args
        sql = execute_call[0][0]
        assert "drug_name" in sql.lower()

    def test_filter_by_section_type(self) -> None:
        """similarity_search supports filtering by section_type."""
        from workshop.src.rag import similarity_search

        conn, cursor = _mock_connection()
        cursor.fetchall.return_value = []

        query_embedding = [0.1] * 3584
        similarity_search(conn, query_embedding, k=5, filters={"section_type": "drug_interactions"})

        execute_call = cursor.execute.call_args
        sql = execute_call[0][0]
        assert "section_type" in sql.lower()
