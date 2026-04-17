"""Tests for src/drug_react.py - ReAct agent loop for drug interactions."""

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


def _make_mock_toolkit():
    """Create a mock ToolKit with realistic tool responses."""
    toolkit = MagicMock()

    toolkit.search_drug_kb.return_value = [
        {
            "drug_name": "WARFARIN SODIUM",
            "section_type": "drug_interactions",
            "set_id": "e98a2d84",
            "text": "Drugs that Increase Bleeding Risk: aspirin, ibuprofen, NSAIDs.",
            "distance": 0.12,
        }
    ]

    def _lookup_interactions(drug_name):
        return [
            {
                "drug_name": drug_name.upper(),
                "section_type": "drug_interactions",
                "set_id": f"set-id-{drug_name}",
                "text": f"Drug interactions for {drug_name}: various interactions noted.",
                "distance": 0.1,
            }
        ]

    toolkit.lookup_interactions.side_effect = _lookup_interactions

    toolkit.lookup_population_warnings.return_value = [
        {
            "drug_name": "IBUPROFEN",
            "section_type": "pregnancy",
            "set_id": "ibu-set-id",
            "text": "Avoid use during third trimester of pregnancy.",
            "distance": 0.15,
        }
    ]

    def _flag_severity(findings):
        result = []
        for f in findings:
            f_copy = dict(f)
            if f.get("source_section_type") == "boxed_warning":
                f_copy["severity"] = "CRITICAL"
            else:
                f_copy["severity"] = "MAJOR"
            result.append(f_copy)
        result.sort(
            key=lambda x: {"CRITICAL": 0, "MAJOR": 1, "MODERATE": 2, "MINOR": 3}.get(x.get("severity", "MINOR"), 3)
        )
        return result

    toolkit.flag_severity.side_effect = _flag_severity

    def _summarize_evidence(findings):
        return [
            {
                "claim": f.get("claim", "Finding"),
                "source_id": f.get("source_id", "unknown"),
                "evidence_snippet": f.get("evidence_snippet", ""),
            }
            for f in findings
        ]

    toolkit.summarize_evidence.side_effect = _summarize_evidence

    return toolkit


def _make_scripted_llm_client(tool_call_sequence):
    """Create an LLM client that returns a scripted sequence of tool calls."""
    client = MagicMock()
    responses = []

    for step in tool_call_sequence:
        mock_response = MagicMock()
        mock_choice = MagicMock()

        if "content" in step:
            mock_choice.message.tool_calls = None
            mock_choice.message.content = step["content"]
        else:
            mock_tool_call = MagicMock()
            mock_tool_call.id = f"call_{step['name']}_{len(responses)}"
            mock_tool_call.function.name = step["name"]
            mock_tool_call.function.arguments = json.dumps(step["arguments"])
            mock_choice.message.tool_calls = [mock_tool_call]
            mock_choice.message.content = step.get("think", "Thinking...")

        mock_response.choices = [mock_choice]
        responses.append(mock_response)

    client.chat.completions.create.side_effect = responses
    return client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRunReactLoop:
    """Test the ReAct agent loop."""

    def test_dispatches_tool_calls_correctly(self) -> None:
        """The loop correctly dispatches tool calls to the toolkit."""
        from src.drug_react import run_react_loop

        toolkit = _make_mock_toolkit()
        llm_client = _make_scripted_llm_client(
            [
                {"name": "lookup_interactions", "arguments": {"drug_name": "warfarin"}, "think": "Checking warfarin"},
                {"content": "Done."},
            ]
        )

        result = run_react_loop(
            query="warfarin interactions",
            toolkit=toolkit,
            llm_client=llm_client,
        )

        toolkit.lookup_interactions.assert_called_once_with(drug_name="warfarin")
        assert "final_response" in result

    def test_respects_max_iterations(self) -> None:
        """The loop terminates after max_iterations even if LLM keeps calling tools."""
        from src.drug_react import run_react_loop

        toolkit = _make_mock_toolkit()
        calls = [
            {"name": "lookup_interactions", "arguments": {"drug_name": f"drug{i}"}, "think": f"Step {i}"}
            for i in range(25)
        ]
        calls.append({"content": "Done."})
        llm_client = _make_scripted_llm_client(calls)

        result = run_react_loop(
            query="too many drugs",
            toolkit=toolkit,
            llm_client=llm_client,
            max_iterations=5,
        )

        assert len(result["trace"]) <= 5

    def test_yields_correct_step_types(self) -> None:
        """The trace log contains think/act/observe entries."""
        from src.drug_react import run_react_loop

        toolkit = _make_mock_toolkit()
        llm_client = _make_scripted_llm_client(
            [
                {"name": "lookup_interactions", "arguments": {"drug_name": "warfarin"}, "think": "I need interactions"},
                {"content": "Analysis complete."},
            ]
        )

        result = run_react_loop(
            query="warfarin interactions",
            toolkit=toolkit,
            llm_client=llm_client,
        )

        trace = result.get("trace", [])
        assert len(trace) >= 1
        entry = trace[0]
        assert "think" in entry
        assert "act" in entry
        assert "observe" in entry

    def test_final_output_structure(self) -> None:
        """The final output has trace, final_response, and tool_results."""
        from src.drug_react import run_react_loop

        toolkit = _make_mock_toolkit()
        llm_client = _make_scripted_llm_client(
            [
                {"name": "search_drug_kb", "arguments": {"query": "test"}, "think": "Testing"},
                {"content": "Result."},
            ]
        )

        result = run_react_loop(
            query="test query",
            toolkit=toolkit,
            llm_client=llm_client,
        )

        assert "trace" in result
        assert "final_response" in result
        assert "tool_results" in result
        assert isinstance(result["trace"], list)
        assert isinstance(result["tool_results"], list)

    def test_handles_tool_error_gracefully(self) -> None:
        """The loop handles tool execution errors without crashing."""
        from src.drug_react import run_react_loop

        toolkit = _make_mock_toolkit()
        toolkit.search_drug_kb.side_effect = Exception("DB connection failed")

        llm_client = _make_scripted_llm_client(
            [
                {"name": "search_drug_kb", "arguments": {"query": "test"}, "think": "Testing"},
                {"content": "Could not complete analysis."},
            ]
        )

        result = run_react_loop(
            query="test query",
            toolkit=toolkit,
            llm_client=llm_client,
        )

        # Should still complete without raising
        assert "final_response" in result
        # Tool error should be captured in tool_results
        assert any("error" in str(tr) for tr in result["tool_results"])
