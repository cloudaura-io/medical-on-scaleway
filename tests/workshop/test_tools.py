"""Tests for workshop/src/tools.py - the five agent tools."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_deps() -> dict:
    """Create mock dependencies (connection, embeddings client, LLM client)."""
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    embeddings_client = MagicMock()
    embeddings_client.embed.return_value = [0.1] * 3584

    llm_client = MagicMock()

    return {
        "conn": conn,
        "cursor": cursor,
        "embeddings_client": embeddings_client,
        "llm_client": llm_client,
    }


def _warfarin_di_row() -> dict:
    """A sample drug_interactions row for warfarin."""
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
        "distance": 0.12,
    }


def _ibuprofen_pregnancy_row() -> dict:
    """A sample pregnancy row for ibuprofen."""
    return {
        "drug_name": "IBUPROFEN",
        "generic_name": "IBUPROFEN",
        "brand_name": "ADVIL",
        "section_type": "pregnancy",
        "set_id": "abc-def-123",
        "application_number": "NDA000001",
        "manufacturer_name": "Test Corp",
        "label_url": "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=e98a2d84",
        "text": "Avoid use during third trimester of pregnancy due to risk of premature closure of the ductus arteriosus.",
        "distance": 0.15,
    }


def _warfarin_boxed_row() -> dict:
    """A sample boxed_warning row for warfarin."""
    return {
        "drug_name": "WARFARIN SODIUM",
        "generic_name": "WARFARIN SODIUM",
        "brand_name": "WARFARIN SODIUM",
        "section_type": "boxed_warning",
        "set_id": "e98a2d84-c192-4d2a-b202-61a81b0c7dda",
        "application_number": "ANDA076807",
        "manufacturer_name": "Taro Pharmaceuticals",
        "label_url": "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=e98a2d84",
        "text": "WARNING: BLEEDING RISK - Warfarin can cause major or fatal bleeding.",
        "distance": 0.05,
    }


# ---------------------------------------------------------------------------
# Tests: search_drug_kb
# ---------------------------------------------------------------------------


class TestSearchDrugKb:
    """Test the search_drug_kb tool."""

    def test_returns_top_k_chunks(self) -> None:
        """search_drug_kb returns chunks with metadata."""
        from workshop.src.tools import ToolKit

        deps = _make_mock_deps()
        deps["cursor"].fetchall.return_value = [_warfarin_di_row()]

        toolkit = ToolKit(
            conn=deps["conn"],
            embeddings_client=deps["embeddings_client"],
            llm_client=deps["llm_client"],
        )

        results = toolkit.search_drug_kb("bleeding risk anticoagulant", top_k=5)

        assert len(results) >= 1
        assert "drug_name" in results[0]
        assert "section_type" in results[0]
        assert "set_id" in results[0]
        assert "text" in results[0]


# ---------------------------------------------------------------------------
# Tests: lookup_interactions
# ---------------------------------------------------------------------------


class TestLookupInteractions:
    """Test the lookup_interactions tool."""

    def test_returns_interaction_chunks(self) -> None:
        """lookup_interactions returns drug_interactions chunks for a drug."""
        from workshop.src.tools import ToolKit

        deps = _make_mock_deps()
        deps["cursor"].fetchall.return_value = [_warfarin_di_row()]

        toolkit = ToolKit(
            conn=deps["conn"],
            embeddings_client=deps["embeddings_client"],
            llm_client=deps["llm_client"],
        )

        results = toolkit.lookup_interactions("warfarin")

        assert len(results) >= 1
        assert results[0]["section_type"] == "drug_interactions"
        assert results[0]["set_id"] == "e98a2d84-c192-4d2a-b202-61a81b0c7dda"

    def test_returns_empty_for_unknown_drug(self) -> None:
        """lookup_interactions returns empty list for unknown drug."""
        from workshop.src.tools import ToolKit

        deps = _make_mock_deps()
        deps["cursor"].fetchall.return_value = []

        toolkit = ToolKit(
            conn=deps["conn"],
            embeddings_client=deps["embeddings_client"],
            llm_client=deps["llm_client"],
        )

        results = toolkit.lookup_interactions("nonexistent_drug_xyz")
        assert results == []


# ---------------------------------------------------------------------------
# Tests: lookup_population_warnings
# ---------------------------------------------------------------------------


class TestLookupPopulationWarnings:
    """Test the lookup_population_warnings tool."""

    def test_returns_pregnancy_chunks(self) -> None:
        """lookup_population_warnings returns pregnancy chunks."""
        from workshop.src.tools import ToolKit

        deps = _make_mock_deps()
        deps["cursor"].fetchall.return_value = [_ibuprofen_pregnancy_row()]

        toolkit = ToolKit(
            conn=deps["conn"],
            embeddings_client=deps["embeddings_client"],
            llm_client=deps["llm_client"],
        )

        results = toolkit.lookup_population_warnings("ibuprofen", "pregnancy")

        assert len(results) >= 1
        assert "third trimester" in results[0]["text"].lower()

    def test_renal_filters_use_in_specific_populations(self) -> None:
        """For renal/hepatic, the tool queries use_in_specific_populations."""
        from workshop.src.tools import ToolKit

        deps = _make_mock_deps()
        renal_row = {
            "drug_name": "METFORMIN",
            "section_type": "use_in_specific_populations",
            "set_id": "met-set-id",
            "text": "Renal impairment: assess eGFR before initiating. Contraindicated if creatinine clearance below 30 mL/min.",
            "distance": 0.1,
        }
        deps["cursor"].fetchall.return_value = [renal_row]

        toolkit = ToolKit(
            conn=deps["conn"],
            embeddings_client=deps["embeddings_client"],
            llm_client=deps["llm_client"],
        )

        results = toolkit.lookup_population_warnings("metformin", "renal")

        assert len(results) >= 1


# ---------------------------------------------------------------------------
# Tests: flag_severity
# ---------------------------------------------------------------------------


class TestFlagSeverity:
    """Test the flag_severity tool."""

    def test_boxed_warning_forced_critical(self) -> None:
        """Any finding from a boxed_warning chunk is forced to CRITICAL."""
        from workshop.src.tools import ToolKit

        deps = _make_mock_deps()

        # Mock LLM to return MODERATE for everything
        mock_choice = MagicMock()
        mock_choice.message.content = "MODERATE"
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        deps["llm_client"].chat.completions.create.return_value = mock_response

        toolkit = ToolKit(
            conn=deps["conn"],
            embeddings_client=deps["embeddings_client"],
            llm_client=deps["llm_client"],
        )

        findings = [
            {
                "claim": "Warfarin can cause major bleeding",
                "source_section_type": "boxed_warning",
                "source_id": "WARFARIN SODIUM :: boxed_warning :: e98a2d84",
                "evidence_snippet": "WARNING: BLEEDING RISK",
            },
            {
                "claim": "Monitor INR closely",
                "source_section_type": "warnings_and_cautions",
                "source_id": "WARFARIN SODIUM :: warnings_and_cautions :: e98a2d84",
                "evidence_snippet": "Regular monitoring of INR should be performed.",
            },
        ]

        result = toolkit.flag_severity(findings)

        # The boxed_warning finding must be CRITICAL
        bw_finding = [f for f in result if f["source_section_type"] == "boxed_warning"][0]
        assert bw_finding["severity"] == "CRITICAL"

    def test_severity_ordering(self) -> None:
        """Results are ordered CRITICAL -> MAJOR -> MODERATE -> MINOR."""
        from workshop.src.tools import ToolKit

        deps = _make_mock_deps()

        # Mock LLM to return different severities per call
        responses = []
        for sev in ["MINOR", "MAJOR"]:
            mock_choice = MagicMock()
            mock_choice.message.content = sev
            mock_response = MagicMock()
            mock_response.choices = [mock_choice]
            responses.append(mock_response)

        deps["llm_client"].chat.completions.create.side_effect = responses

        toolkit = ToolKit(
            conn=deps["conn"],
            embeddings_client=deps["embeddings_client"],
            llm_client=deps["llm_client"],
        )

        findings = [
            {
                "claim": "Minor issue",
                "source_section_type": "geriatric_use",
                "source_id": "DRUG :: geriatric_use :: id1",
                "evidence_snippet": "Some minor finding.",
            },
            {
                "claim": "Major bleeding risk",
                "source_section_type": "drug_interactions",
                "source_id": "DRUG :: drug_interactions :: id2",
                "evidence_snippet": "Significant bleeding risk.",
            },
        ]

        result = toolkit.flag_severity(findings)

        severities = [f["severity"] for f in result]
        severity_order = {"CRITICAL": 0, "MAJOR": 1, "MODERATE": 2, "MINOR": 3}
        ordered_values = [severity_order.get(s, 99) for s in severities]
        assert ordered_values == sorted(ordered_values), f"Severities not in order: {severities}"


# ---------------------------------------------------------------------------
# Tests: summarize_evidence
# ---------------------------------------------------------------------------


class TestSummarizeEvidence:
    """Test the summarize_evidence tool."""

    def test_output_structure(self) -> None:
        """summarize_evidence returns JSON with claim/source_id/evidence_snippet triples."""
        from workshop.src.tools import ToolKit

        deps = _make_mock_deps()

        # Mock LLM to return structured JSON
        summary_json = json.dumps(
            [
                {
                    "claim": "Warfarin + aspirin increases bleeding risk",
                    "source_id": "WARFARIN SODIUM :: drug_interactions :: e98a2d84",
                    "evidence_snippet": "Drugs that Increase Bleeding Risk: aspirin",
                }
            ]
        )
        mock_choice = MagicMock()
        mock_choice.message.content = summary_json
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        deps["llm_client"].chat.completions.create.return_value = mock_response

        toolkit = ToolKit(
            conn=deps["conn"],
            embeddings_client=deps["embeddings_client"],
            llm_client=deps["llm_client"],
        )

        findings = [
            {
                "claim": "Warfarin + aspirin increases bleeding risk",
                "source_id": "WARFARIN SODIUM :: drug_interactions :: e98a2d84",
                "evidence_snippet": "Drugs that Increase Bleeding Risk: aspirin",
                "severity": "MAJOR",
                "source_section_type": "drug_interactions",
            }
        ]

        result = toolkit.summarize_evidence(findings)

        assert isinstance(result, list)
        assert len(result) >= 1
        item = result[0]
        assert "claim" in item
        assert "source_id" in item
        assert "evidence_snippet" in item

    def test_source_id_format(self) -> None:
        """source_id follows the <drug_name> :: <section_type> :: <set_id> format."""
        from workshop.src.tools import ToolKit

        deps = _make_mock_deps()

        summary_json = json.dumps(
            [
                {
                    "claim": "Test claim",
                    "source_id": "WARFARIN SODIUM :: drug_interactions :: e98a2d84-c192-4d2a-b202-61a81b0c7dda",
                    "evidence_snippet": "Test evidence",
                }
            ]
        )
        mock_choice = MagicMock()
        mock_choice.message.content = summary_json
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        deps["llm_client"].chat.completions.create.return_value = mock_response

        toolkit = ToolKit(
            conn=deps["conn"],
            embeddings_client=deps["embeddings_client"],
            llm_client=deps["llm_client"],
        )

        findings = [
            {
                "claim": "Test claim",
                "source_id": "WARFARIN SODIUM :: drug_interactions :: e98a2d84-c192-4d2a-b202-61a81b0c7dda",
                "evidence_snippet": "Test evidence",
                "severity": "MAJOR",
                "source_section_type": "drug_interactions",
            }
        ]

        result = toolkit.summarize_evidence(findings)

        source_id = result[0]["source_id"]
        parts = source_id.split(" :: ")
        assert len(parts) == 3, f"source_id should have 3 parts separated by ' :: ', got: {source_id}"
