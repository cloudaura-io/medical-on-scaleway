"""Tests for src/drug_rag.py - pgvector helpers for drug interaction chunks."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_conn():
    """Create a mock psycopg connection with cursor context manager."""
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return conn, cursor


def _sample_chunk():
    """Return a sample drug chunk dict."""
    return {
        "drug_name": "WARFARIN SODIUM",
        "generic_name": "WARFARIN SODIUM",
        "brand_name": "WARFARIN SODIUM",
        "section_type": "drug_interactions",
        "set_id": "e98a2d84-c192-4d2a-b202-61a81b0c7dda",
        "application_number": "ANDA076807",
        "manufacturer_name": "Taro Pharmaceuticals",
        "label_url": "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=e98a2d84",
        "text": "Drugs that Increase Bleeding Risk: aspirin, ibuprofen, NSAIDs.",
        "embedding": [0.1] * 3584,
    }


# ---------------------------------------------------------------------------
# Tests: create_drug_table
# ---------------------------------------------------------------------------


class TestCreateDrugTable:
    """Test create_drug_table creates correct schema with vector(768) column."""

    def test_creates_table_with_vector_column(self) -> None:
        """create_drug_table executes CREATE TABLE with vector(768) column."""
        from src.drug_rag import create_drug_table

        conn, cursor = _make_mock_conn()
        create_drug_table(conn)

        # Check that cursor.execute was called with SQL containing vector(768)
        all_sql = " ".join(str(c) for c in cursor.execute.call_args_list)
        assert "drug_chunks" in all_sql
        assert "vector(768)" in all_sql

    def test_creates_hnsw_index(self) -> None:
        """create_drug_table creates an HNSW index."""
        from src.drug_rag import create_drug_table

        conn, cursor = _make_mock_conn()
        create_drug_table(conn)

        all_sql = " ".join(str(c) for c in cursor.execute.call_args_list)
        assert "hnsw" in all_sql.lower()

    def test_commits_transaction(self) -> None:
        """create_drug_table commits the transaction."""
        from src.drug_rag import create_drug_table

        conn, cursor = _make_mock_conn()
        create_drug_table(conn)

        conn.commit.assert_called()


# ---------------------------------------------------------------------------
# Tests: insert_drug_chunks
# ---------------------------------------------------------------------------


class TestInsertDrugChunks:
    """Test insert_drug_chunks bulk inserts chunks correctly."""

    def test_inserts_all_chunks(self) -> None:
        """insert_drug_chunks inserts each chunk into the database."""
        from src.drug_rag import insert_drug_chunks

        conn, cursor = _make_mock_conn()
        chunks = [_sample_chunk(), _sample_chunk()]

        insert_drug_chunks(conn, chunks)

        assert cursor.execute.call_count == 2

    def test_commits_after_insert(self) -> None:
        """insert_drug_chunks commits the transaction."""
        from src.drug_rag import insert_drug_chunks

        conn, cursor = _make_mock_conn()
        insert_drug_chunks(conn, [_sample_chunk()])

        conn.commit.assert_called()

    def test_handles_empty_list(self) -> None:
        """insert_drug_chunks handles empty chunk list gracefully."""
        from src.drug_rag import insert_drug_chunks

        conn, cursor = _make_mock_conn()
        insert_drug_chunks(conn, [])

        cursor.execute.assert_not_called()
        conn.commit.assert_called()


# ---------------------------------------------------------------------------
# Tests: drug_similarity_search
# ---------------------------------------------------------------------------


class TestDrugSimilaritySearch:
    """Test drug_similarity_search returns ranked results with correct metadata."""

    def test_returns_ranked_results(self) -> None:
        """drug_similarity_search returns results from the database."""
        from src.drug_rag import drug_similarity_search

        conn, cursor = _make_mock_conn()
        cursor.fetchall.return_value = [
            {
                "drug_name": "WARFARIN SODIUM",
                "generic_name": "WARFARIN SODIUM",
                "brand_name": "WARFARIN SODIUM",
                "section_type": "drug_interactions",
                "set_id": "e98a2d84",
                "application_number": "ANDA076807",
                "manufacturer_name": "Taro",
                "label_url": "https://api.fda.gov/...",
                "text": "Aspirin increases bleeding risk",
                "distance": 0.12,
            }
        ]

        query_embedding = [0.1] * 3584
        results = drug_similarity_search(conn, query_embedding, k=5)

        assert len(results) == 1
        assert results[0]["drug_name"] == "WARFARIN SODIUM"
        assert results[0]["section_type"] == "drug_interactions"

    def test_filters_by_drug_name(self) -> None:
        """drug_similarity_search applies drug_name filter."""
        from src.drug_rag import drug_similarity_search

        conn, cursor = _make_mock_conn()
        cursor.fetchall.return_value = []

        drug_similarity_search(conn, [0.1] * 3584, k=5, filters={"drug_name": "warfarin"})

        sql_called = str(cursor.execute.call_args)
        assert "drug_name" in sql_called.lower()

    def test_filters_by_section_type(self) -> None:
        """drug_similarity_search applies section_type filter."""
        from src.drug_rag import drug_similarity_search

        conn, cursor = _make_mock_conn()
        cursor.fetchall.return_value = []

        drug_similarity_search(
            conn,
            [0.1] * 3584,
            k=5,
            filters={"section_type": "drug_interactions"},
        )

        sql_called = str(cursor.execute.call_args)
        assert "section_type" in sql_called.lower()

    def test_returns_empty_for_no_matches(self) -> None:
        """drug_similarity_search returns empty list when no matches found."""
        from src.drug_rag import drug_similarity_search

        conn, cursor = _make_mock_conn()
        cursor.fetchall.return_value = []

        results = drug_similarity_search(conn, [0.1] * 3584)
        assert results == []
