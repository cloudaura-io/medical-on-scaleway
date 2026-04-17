"""Tests for src/drug_tools.py - the five agent tools for drug interactions."""

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


def _make_mock_deps():
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


def _warfarin_di_row():
    """A sample drug_interactions row for warfarin."""
    return {
        "drug_name": "WARFARIN SODIUM",
        "generic_name": "WARFARIN SODIUM",
        "brand_name": "WARFARIN SODIUM",
        "section_type": "drug_interactions",
        "set_id": "e98a2d84-c192-4d2a-b202-61a81b0c7dda",
        "application_number": "ANDA076807",
        "manufacturer_name": "Taro Pharmaceuticals",
        "source_url": "https://api.fda.gov/drug/label.json?search=openfda.set_id:e98a2d84",
        "text": "Drugs that Increase Bleeding Risk: aspirin, ibuprofen, NSAIDs.",
        "distance": 0.12,
    }


def _ibuprofen_pregnancy_row():
    """A sample pregnancy row for ibuprofen."""
    return {
        "drug_name": "IBUPROFEN",
        "generic_name": "IBUPROFEN",
        "brand_name": "ADVIL",
        "section_type": "pregnancy",
        "set_id": "abc-def-123",
        "application_number": "NDA000001",
        "manufacturer_name": "Test Corp",
        "source_url": "https://api.fda.gov/drug/label.json",
        "text": "Avoid use during third trimester of pregnancy due to risk of premature closure of the ductus arteriosus.",
        "distance": 0.15,
    }


# ---------------------------------------------------------------------------
# Tests: search_drug_kb
# ---------------------------------------------------------------------------


class TestSearchDrugKb:
    """Test the search_drug_kb tool."""

    def test_returns_relevant_chunks(self) -> None:
        """search_drug_kb returns chunks with metadata."""
        from src.drug_tools import ToolKit

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

    def test_filters_by_drug_interactions_section(self) -> None:
        """lookup_interactions filters by drug_interactions section type."""
        from src.drug_tools import ToolKit

        deps = _make_mock_deps()
        deps["cursor"].fetchall.return_value = [_warfarin_di_row()]

        toolkit = ToolKit(
            conn=deps["conn"],
            embeddings_client=deps["embeddings_client"],
            llm_client=deps["llm_client"],
        )

        results = toolkit.lookup_interactions("warfarin")

        assert len(results) >= 1
        # Verify the embedding was called with drug interactions query
        deps["embeddings_client"].embed.assert_called()
        embed_arg = deps["embeddings_client"].embed.call_args[0][0]
        assert "warfarin" in embed_arg.lower()
        assert "interaction" in embed_arg.lower()

    def test_returns_empty_for_unknown_drug(self) -> None:
        """lookup_interactions returns empty list for unknown drug."""
        from src.drug_tools import ToolKit

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

    def test_maps_pregnancy_to_correct_section(self) -> None:
        """lookup_population_warnings maps 'pregnancy' to pregnancy section type."""
        from src.drug_tools import ToolKit

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

    def test_maps_pediatric_to_correct_section(self) -> None:
        """lookup_population_warnings maps 'pediatric' to pediatric_use."""
        from src.drug_tools import ToolKit

        deps = _make_mock_deps()
        deps["cursor"].fetchall.return_value = []

        toolkit = ToolKit(
            conn=deps["conn"],
            embeddings_client=deps["embeddings_client"],
            llm_client=deps["llm_client"],
        )

        toolkit.lookup_population_warnings("ibuprofen", "pediatric")

        # Verify the SQL filter includes pediatric_use
        sql_called = str(deps["cursor"].execute.call_args)
        assert "pediatric_use" in sql_called

    def test_renal_filters_by_keyword(self) -> None:
        """For renal population, results are filtered by renal keywords."""
        from src.drug_tools import ToolKit

        deps = _make_mock_deps()
        renal_row = {
            "drug_name": "METFORMIN",
            "section_type": "use_in_specific_populations",
            "set_id": "met-set-id",
            "text": "Renal impairment: assess eGFR before initiating.",
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

    def test_unknown_population_returns_empty(self) -> None:
        """lookup_population_warnings returns empty for unknown population."""
        from src.drug_tools import ToolKit

        deps = _make_mock_deps()

        toolkit = ToolKit(
            conn=deps["conn"],
            embeddings_client=deps["embeddings_client"],
            llm_client=deps["llm_client"],
        )

        results = toolkit.lookup_population_warnings("ibuprofen", "unknown_pop")
        assert results == []


# ---------------------------------------------------------------------------
# Tests: flag_severity
# ---------------------------------------------------------------------------


class TestFlagSeverity:
    """Test the flag_severity tool."""

    def test_boxed_warning_forced_critical(self) -> None:
        """Any finding from a boxed_warning chunk is forced to CRITICAL."""
        from src.drug_tools import ToolKit

        deps = _make_mock_deps()

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
                "source_id": "WARFARIN :: boxed_warning :: e98a2d84",
                "evidence_snippet": "WARNING: BLEEDING RISK",
            },
            {
                "claim": "Monitor INR closely",
                "source_section_type": "warnings_and_cautions",
                "source_id": "WARFARIN :: warnings_and_cautions :: e98a2d84",
                "evidence_snippet": "Regular monitoring of INR.",
            },
        ]

        result = toolkit.flag_severity(findings)

        bw = [f for f in result if f["source_section_type"] == "boxed_warning"][0]
        assert bw["severity"] == "CRITICAL"

    def test_classifies_and_reorders_findings(self) -> None:
        """Results are ordered CRITICAL -> MAJOR -> MODERATE -> MINOR."""
        from src.drug_tools import ToolKit

        deps = _make_mock_deps()

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
        ordered = [severity_order.get(s, 99) for s in severities]
        assert ordered == sorted(ordered), f"Severities not in order: {severities}"


# ---------------------------------------------------------------------------
# Tests: summarize_evidence
# ---------------------------------------------------------------------------


class TestSummarizeEvidence:
    """Test the summarize_evidence tool."""

    def test_produces_report_with_citations(self) -> None:
        """summarize_evidence returns JSON with claim/source_id/evidence_snippet."""
        from src.drug_tools import ToolKit

        deps = _make_mock_deps()

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
