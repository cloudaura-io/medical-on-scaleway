"""Tests for src/drug_chunker.py - FDA label section chunker."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _sample_label():
    """Return a minimal openFDA label with multiple sections."""
    return {
        "openfda": {
            "generic_name": ["WARFARIN SODIUM"],
            "brand_name": ["COUMADIN"],
            "spl_set_id": ["e98a2d84-c192-4d2a-b202-61a81b0c7dda"],
            "application_number": ["ANDA076807"],
            "manufacturer_name": ["Taro Pharmaceuticals"],
        },
        "boxed_warning": ["WARNING: BLEEDING RISK - Warfarin can cause major or fatal bleeding."],
        "drug_interactions": ["Drugs that increase bleeding risk include aspirin, NSAIDs."],
        "drug_interactions_table": ["| Drug | Effect |\n| Aspirin | Increased bleeding |"],
        "contraindications": ["Contraindicated in pregnancy."],
        "pregnancy": ["Warfarin is contraindicated in pregnancy. Category X."],
        "geriatric_use": ["Elderly patients may be more sensitive to warfarin."],
    }


# ---------------------------------------------------------------------------
# Tests: chunk_label
# ---------------------------------------------------------------------------


class TestChunkLabel:
    """Test chunk_label extracts all expected section types."""

    def test_extracts_all_present_sections(self) -> None:
        """chunk_label creates one chunk per chunkable section present in the label."""
        from src.drug_chunker import chunk_label

        label = _sample_label()
        chunks = chunk_label(label)

        section_types = {c["section_type"] for c in chunks}
        assert "boxed_warning" in section_types
        assert "drug_interactions" in section_types
        assert "contraindications" in section_types
        assert "pregnancy" in section_types
        assert "geriatric_use" in section_types

    def test_skips_missing_sections(self) -> None:
        """chunk_label does not create chunks for sections absent from the label."""
        from src.drug_chunker import chunk_label

        label = _sample_label()
        chunks = chunk_label(label)

        section_types = {c["section_type"] for c in chunks}
        # These sections are not in _sample_label
        assert "pediatric_use" not in section_types
        assert "adverse_reactions" not in section_types

    def test_metadata_extraction(self) -> None:
        """chunk_label extracts generic_name, brand_name, set_id, label_url."""
        from src.drug_chunker import chunk_label

        label = _sample_label()
        chunks = chunk_label(label)

        for chunk in chunks:
            assert chunk["generic_name"] == "WARFARIN SODIUM"
            assert chunk["brand_name"] == "COUMADIN"
            assert chunk["set_id"] == "e98a2d84-c192-4d2a-b202-61a81b0c7dda"
            assert "label_url" in chunk
            assert chunk["label_url"].startswith("https://dailymed.nlm.nih.gov/")
            assert chunk["set_id"] in chunk["label_url"]

    def test_drug_name_field(self) -> None:
        """chunk_label sets drug_name from generic_name."""
        from src.drug_chunker import chunk_label

        label = _sample_label()
        chunks = chunk_label(label)

        for chunk in chunks:
            assert chunk["drug_name"] == "WARFARIN SODIUM"

    def test_drug_interactions_table_folding(self) -> None:
        """drug_interactions_table is folded into the drug_interactions chunk text."""
        from src.drug_chunker import chunk_label

        label = _sample_label()
        chunks = chunk_label(label)

        di_chunks = [c for c in chunks if c["section_type"] == "drug_interactions"]
        assert len(di_chunks) == 1
        assert "Drug Interactions Table" in di_chunks[0]["text"]
        assert "Aspirin" in di_chunks[0]["text"]

    def test_empty_label(self) -> None:
        """chunk_label returns empty list for a label with no chunkable sections."""
        from src.drug_chunker import chunk_label

        label = {"openfda": {"generic_name": ["ASPIRIN"]}}
        chunks = chunk_label(label)

        assert chunks == []

    def test_list_section_values(self) -> None:
        """chunk_label joins list section values with newlines."""
        from src.drug_chunker import chunk_label

        label = {
            "openfda": {"generic_name": ["TEST DRUG"]},
            "contraindications": ["Do not use if allergic.", "Do not use with MAOIs."],
        }
        chunks = chunk_label(label)

        assert len(chunks) == 1
        assert "Do not use if allergic." in chunks[0]["text"]
        assert "Do not use with MAOIs." in chunks[0]["text"]
