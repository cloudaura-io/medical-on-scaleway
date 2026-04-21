"""Tests for scripts/init_drug_db.py - database initialization."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sample_labels():
    """Return a small list of sample openFDA labels."""
    return [
        {
            "openfda": {
                "generic_name": ["WARFARIN SODIUM"],
                "brand_name": ["COUMADIN"],
                "spl_set_id": ["e98a2d84"],
            },
            "drug_interactions": ["Aspirin increases bleeding risk."],
            "contraindications": ["Contraindicated in pregnancy."],
        },
        {
            "openfda": {
                "generic_name": ["IBUPROFEN"],
                "brand_name": ["ADVIL"],
                "spl_set_id": ["ibu-123"],
            },
            "drug_interactions": ["Avoid with anticoagulants."],
            "pregnancy": ["Avoid in third trimester."],
        },
    ]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestInitDrugDb:
    """Test the init_drug_db script functions."""

    def test_reads_openfda_labels_correctly(self, tmp_path: Path) -> None:
        """The script correctly reads and parses openfda_labels.json."""
        from scripts.init_drug_db import load_labels

        labels = _sample_labels()
        data_file = tmp_path / "openfda_labels.json"
        data_file.write_text(json.dumps(labels))

        loaded = load_labels(str(data_file))

        assert len(loaded) == 2
        assert loaded[0]["openfda"]["generic_name"] == ["WARFARIN SODIUM"]

    def test_chunk_all_labels(self) -> None:
        """chunk_all_labels produces the expected number of chunks."""
        from scripts.init_drug_db import chunk_all_labels

        labels = _sample_labels()
        chunks = chunk_all_labels(labels)

        # Warfarin has 2 sections (drug_interactions, contraindications)
        # Ibuprofen has 2 sections (drug_interactions, pregnancy)
        assert len(chunks) == 4

    def test_chunk_all_labels_metadata(self) -> None:
        """chunk_all_labels preserves metadata in each chunk."""
        from scripts.init_drug_db import chunk_all_labels

        labels = _sample_labels()
        chunks = chunk_all_labels(labels)

        for chunk in chunks:
            assert "drug_name" in chunk
            assert "section_type" in chunk
            assert "text" in chunk
            assert "set_id" in chunk

    def test_idempotent_table_creation(self) -> None:
        """seed_database drops and recreates the drug_chunks table."""
        from scripts.init_drug_db import seed_database

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        mock_embeddings = MagicMock()
        mock_embeddings.embed_batch.return_value = [[0.1] * 3584]

        chunks = [
            {
                "drug_name": "TEST",
                "generic_name": "TEST",
                "brand_name": "TEST",
                "section_type": "drug_interactions",
                "set_id": "test-id",
                "label_url": "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=test-id",
                "text": "Test text",
            }
        ]

        seed_database(mock_conn, mock_embeddings, chunks, batch_size=10)

        # Verify DROP TABLE was called
        all_sql = " ".join(str(c) for c in mock_cursor.execute.call_args_list)
        assert "drop table" in all_sql.lower()
