"""Tests for workshop/scripts/fetch_openfda_labels.py - openFDA label fetcher."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Ensure workshop packages are importable
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_fixture() -> dict:
    """Load the recorded openFDA warfarin fixture."""
    with open(FIXTURES_DIR / "openfda_warfarin.json") as f:
        return json.load(f)


def _mock_response(fixture: dict, status_code: int = 200) -> MagicMock:
    """Create a mock requests.Response from the fixture."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = fixture
    resp.raise_for_status.return_value = None
    return resp


# ---------------------------------------------------------------------------
# Kept and dropped sections (must stay in sync with spec)
# ---------------------------------------------------------------------------

KEPT_SECTIONS = [
    "boxed_warning",
    "indications_and_usage",
    "contraindications",
    "warnings_and_cautions",
    "drug_interactions",
    "drug_interactions_table",
    "adverse_reactions",
    "use_in_specific_populations",
    "pregnancy",
    "pediatric_use",
    "geriatric_use",
    "mechanism_of_action",
    "clinical_pharmacology",
]

DROPPED_SECTIONS = [
    "spl_product_data_elements",
    "references",
    "how_supplied",
    "clinical_studies_table",
    "dosage_forms_and_strengths",
    "nonclinical_toxicology",
]

KEPT_METADATA_FIELDS = [
    "generic_name",
    "brand_name",
    "rxcui",
    "application_number",
    "product_ndc",
    "manufacturer_name",
    "set_id",
]


# ---------------------------------------------------------------------------
# Tests: Section trimming
# ---------------------------------------------------------------------------


class TestSectionTrimming:
    """Verify that the fetcher keeps only the specified sections."""

    def test_kept_sections_present(self) -> None:
        """All kept sections that exist in the raw API response must survive trimming."""
        from workshop.scripts.fetch_openfda_labels import fetch_labels

        fixture = _load_fixture()
        mock_resp = _mock_response(fixture)

        with (
            patch("workshop.scripts.fetch_openfda_labels.requests.get", return_value=mock_resp),
            patch("workshop.scripts.fetch_openfda_labels.time.sleep"),
        ):
            results = fetch_labels(drug_names=["warfarin"])

        assert len(results) == 1
        record = results[0]

        for section in KEPT_SECTIONS:
            # The fixture has all kept sections; they must be present after trimming
            assert section in record, f"Expected kept section '{section}' not found in result"

    def test_dropped_sections_absent(self) -> None:
        """Sections not in the kept list must be dropped."""
        from workshop.scripts.fetch_openfda_labels import fetch_labels

        fixture = _load_fixture()
        mock_resp = _mock_response(fixture)

        with (
            patch("workshop.scripts.fetch_openfda_labels.requests.get", return_value=mock_resp),
            patch("workshop.scripts.fetch_openfda_labels.time.sleep"),
        ):
            results = fetch_labels(drug_names=["warfarin"])

        assert len(results) == 1
        record = results[0]

        for section in DROPPED_SECTIONS:
            assert section not in record, f"Dropped section '{section}' should not be in result"

    def test_openfda_metadata_present(self) -> None:
        """The openfda metadata block must carry all expected fields."""
        from workshop.scripts.fetch_openfda_labels import fetch_labels

        fixture = _load_fixture()
        mock_resp = _mock_response(fixture)

        with (
            patch("workshop.scripts.fetch_openfda_labels.requests.get", return_value=mock_resp),
            patch("workshop.scripts.fetch_openfda_labels.time.sleep"),
        ):
            results = fetch_labels(drug_names=["warfarin"])

        record = results[0]
        assert "openfda" in record, "openfda metadata block missing"
        openfda = record["openfda"]

        for field in KEPT_METADATA_FIELDS:
            assert field in openfda, f"Expected openfda field '{field}' not found"


# ---------------------------------------------------------------------------
# Tests: Polite pacing
# ---------------------------------------------------------------------------


class TestPolitePacing:
    """Verify the fetcher respects rate-limiting conventions."""

    def test_sleeps_between_requests(self) -> None:
        """Between requests the fetcher must sleep >= 1 second."""
        from workshop.scripts.fetch_openfda_labels import fetch_labels

        fixture = _load_fixture()
        mock_resp = _mock_response(fixture)

        with (
            patch("workshop.scripts.fetch_openfda_labels.requests.get", return_value=mock_resp),
            patch("workshop.scripts.fetch_openfda_labels.time.sleep") as mock_sleep,
        ):
            fetch_labels(drug_names=["warfarin", "aspirin"])

        # With 2 drugs, at least 1 sleep call between them
        assert mock_sleep.call_count >= 1, "Expected at least one sleep call between requests"
        for call in mock_sleep.call_args_list:
            delay = call[0][0]
            assert delay >= 1.0, f"Sleep delay {delay}s is less than the 1s minimum"

    def test_retries_on_429(self) -> None:
        """On HTTP 429 the fetcher must back off and retry."""
        from workshop.scripts.fetch_openfda_labels import fetch_labels

        fixture = _load_fixture()

        # First call returns 429, second returns 200
        resp_429 = MagicMock()
        resp_429.status_code = 429
        resp_429.raise_for_status.side_effect = Exception("429 Too Many Requests")

        resp_200 = _mock_response(fixture)

        with (
            patch(
                "workshop.scripts.fetch_openfda_labels.requests.get",
                side_effect=[resp_429, resp_200],
            ),
            patch("workshop.scripts.fetch_openfda_labels.time.sleep") as mock_sleep,
        ):
            results = fetch_labels(drug_names=["warfarin"])

        assert len(results) == 1
        # Must have slept at least once for the backoff
        backoff_calls = [c for c in mock_sleep.call_args_list if c[0][0] > 1.0]
        assert len(backoff_calls) >= 1, "Expected at least one backoff sleep after 429"
