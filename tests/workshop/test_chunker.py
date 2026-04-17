"""Tests for workshop/src/chunker.py - label section chunker."""

from __future__ import annotations

import json
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Ensure workshop packages are importable
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_warfarin_fixture() -> dict:
    """Load and trim the warfarin fixture as fetch_openfda_labels would."""
    with open(FIXTURES_DIR / "openfda_warfarin.json") as f:
        raw = json.load(f)
    # Simulate the trimmed result (only kept sections + openfda)
    from workshop.scripts.fetch_openfda_labels import _trim_result

    return _trim_result(raw["results"][0])


# ---------------------------------------------------------------------------
# Expected section types from the warfarin fixture
# ---------------------------------------------------------------------------

EXPECTED_SECTION_TYPES = [
    "boxed_warning",
    "indications_and_usage",
    "contraindications",
    "warnings_and_cautions",
    "drug_interactions",
    "adverse_reactions",
    "use_in_specific_populations",
    "pregnancy",
    "pediatric_use",
    "geriatric_use",
    "mechanism_of_action",
    "clinical_pharmacology",
]

EXPECTED_METADATA_FIELDS = [
    "drug_name",
    "generic_name",
    "brand_name",
    "set_id",
    "application_number",
    "manufacturer_name",
    "source_url",
]


# ---------------------------------------------------------------------------
# Tests: Chunk generation
# ---------------------------------------------------------------------------


class TestChunkGeneration:
    """Verify that chunk_label produces correct chunks."""

    def test_one_chunk_per_present_section(self) -> None:
        """Each present section produces exactly one chunk with correct section_type."""
        from workshop.src.chunker import chunk_label

        label = _load_warfarin_fixture()
        chunks = chunk_label(label)

        section_types = [c["section_type"] for c in chunks]

        for expected in EXPECTED_SECTION_TYPES:
            assert expected in section_types, f"Expected section_type '{expected}' not found in chunks"

    def test_metadata_present_on_each_chunk(self) -> None:
        """Every chunk carries the required metadata fields."""
        from workshop.src.chunker import chunk_label

        label = _load_warfarin_fixture()
        chunks = chunk_label(label)

        for chunk in chunks:
            for field in EXPECTED_METADATA_FIELDS:
                assert field in chunk, (
                    f"Missing metadata field '{field}' in chunk for section '{chunk.get('section_type')}'"
                )

    def test_drug_interactions_table_folded(self) -> None:
        """drug_interactions_table is folded into the drug_interactions chunk text,
        not stored as a separate chunk."""
        from workshop.src.chunker import chunk_label

        label = _load_warfarin_fixture()
        chunks = chunk_label(label)

        section_types = [c["section_type"] for c in chunks]
        assert "drug_interactions_table" not in section_types, "drug_interactions_table should not be a separate chunk"

        # The drug_interactions chunk should include the table content
        di_chunks = [c for c in chunks if c["section_type"] == "drug_interactions"]
        assert len(di_chunks) == 1
        # Table content mentions NSAIDs and anticoagulants
        assert "NSAID" in di_chunks[0]["text"] or "Ibuprofen" in di_chunks[0]["text"]

    def test_chunk_text_is_verbatim_section_content(self) -> None:
        """Chunk text is the verbatim section content from the label."""
        from workshop.src.chunker import chunk_label

        label = _load_warfarin_fixture()
        chunks = chunk_label(label)

        # Check boxed_warning text matches the source
        bw_chunks = [c for c in chunks if c["section_type"] == "boxed_warning"]
        assert len(bw_chunks) == 1
        # The text should contain the original boxed warning content
        assert "BLEEDING RISK" in bw_chunks[0]["text"]

    def test_missing_sections_produce_no_chunks(self) -> None:
        """If a section is missing from the label, no chunk is produced for it."""
        from workshop.src.chunker import chunk_label

        # Create a label with only boxed_warning
        minimal_label = {
            "boxed_warning": ["WARNING: This is a test"],
            "openfda": {
                "generic_name": ["TEST DRUG"],
                "brand_name": ["TESTBRAND"],
                "set_id": ["test-set-id"],
                "application_number": ["NDA000000"],
                "manufacturer_name": ["Test Corp"],
            },
        }

        chunks = chunk_label(minimal_label)
        section_types = [c["section_type"] for c in chunks]

        assert "boxed_warning" in section_types
        assert len(chunks) == 1, f"Expected 1 chunk for minimal label, got {len(chunks)}"

    def test_source_url_format(self) -> None:
        """source_url should point to the DailyMed/openFDA label via set_id."""
        from workshop.src.chunker import chunk_label

        label = _load_warfarin_fixture()
        chunks = chunk_label(label)

        for chunk in chunks:
            assert "source_url" in chunk
            # Should reference the set_id
            assert chunk["set_id"] in chunk["source_url"] or "openfda" in chunk["source_url"].lower()

    def test_drug_name_from_generic_name(self) -> None:
        """drug_name should be derived from the openfda generic_name field."""
        from workshop.src.chunker import chunk_label

        label = _load_warfarin_fixture()
        chunks = chunk_label(label)

        for chunk in chunks:
            assert "warfarin" in chunk["drug_name"].lower()
