"""Tests for workshop/src/react_loop.py - ReAct agent loop."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_toolkit() -> MagicMock:
    """Create a mock ToolKit with realistic tool responses."""
    toolkit = MagicMock()

    # search_drug_kb returns a generic result
    toolkit.search_drug_kb.return_value = [
        {
            "drug_name": "WARFARIN SODIUM",
            "section_type": "drug_interactions",
            "set_id": "e98a2d84",
            "text": "Drugs that Increase Bleeding Risk: aspirin, ibuprofen, NSAIDs.",
            "distance": 0.12,
        }
    ]

    # lookup_interactions returns drug-specific results
    def _lookup_interactions(drug_name: str) -> list:
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

    # lookup_population_warnings
    toolkit.lookup_population_warnings.return_value = [
        {
            "drug_name": "IBUPROFEN",
            "section_type": "pregnancy",
            "set_id": "ibu-set-id",
            "text": "Avoid use during third trimester of pregnancy.",
            "distance": 0.15,
        }
    ]

    # flag_severity returns sorted findings
    def _flag_severity(findings: list) -> list:
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

    # summarize_evidence returns structured output
    def _summarize_evidence(findings: list) -> list:
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


def _make_scripted_llm_client(tool_call_sequence: list[dict]) -> MagicMock:
    """Create an LLM client that returns a scripted sequence of tool calls.

    Each item in tool_call_sequence is either:
    - A dict with 'name' and 'arguments' -> triggers a tool call
    - A dict with 'content' -> returns a final text response (terminates loop)
    """
    client = MagicMock()
    responses = []

    for step in tool_call_sequence:
        mock_response = MagicMock()
        mock_choice = MagicMock()

        if "content" in step:
            # Final response - no tool calls
            mock_choice.message.tool_calls = None
            mock_choice.message.content = step["content"]
            mock_choice.finish_reason = "stop"
        else:
            # Tool call
            mock_tool_call = MagicMock()
            mock_tool_call.id = f"call_{step['name']}_{len(responses)}"
            mock_tool_call.function.name = step["name"]
            mock_tool_call.function.arguments = json.dumps(step["arguments"])
            mock_choice.message.tool_calls = [mock_tool_call]
            mock_choice.message.content = step.get("think", "Thinking...")
            mock_choice.finish_reason = "tool_calls"

        mock_response.choices = [mock_choice]
        responses.append(mock_response)

    client.chat.completions.create.side_effect = responses
    return client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestReActLoop:
    """Test the ReAct agent loop."""

    def test_canonical_query_exercises_all_tools(self) -> None:
        """The canonical warfarin+aspirin+ibuprofen+pregnancy query exercises all five tools."""
        from workshop.src.react_loop import run_react_loop

        toolkit = _make_mock_toolkit()

        # Script the LLM to call tools in the expected order
        llm_client = _make_scripted_llm_client(
            [
                {
                    "name": "lookup_interactions",
                    "arguments": {"drug_name": "warfarin"},
                    "think": "Need to check warfarin interactions",
                },
                {
                    "name": "lookup_interactions",
                    "arguments": {"drug_name": "aspirin"},
                    "think": "Now checking aspirin interactions",
                },
                {
                    "name": "lookup_interactions",
                    "arguments": {"drug_name": "ibuprofen"},
                    "think": "Now checking ibuprofen interactions",
                },
                {
                    "name": "lookup_population_warnings",
                    "arguments": {"drug_name": "ibuprofen", "population": "pregnancy"},
                    "think": "Patient is pregnant, check ibuprofen pregnancy warnings",
                },
                {
                    "name": "search_drug_kb",
                    "arguments": {"query": "NSAID bleeding risk pregnancy"},
                    "think": "Let me search for additional context",
                },
                {
                    "name": "flag_severity",
                    "arguments": {
                        "findings": [
                            {
                                "claim": "Warfarin + aspirin increases bleeding risk",
                                "source_section_type": "drug_interactions",
                                "source_id": "WARFARIN :: drug_interactions :: e98a2d84",
                                "evidence_snippet": "aspirin increases bleeding risk",
                            },
                            {
                                "claim": "Ibuprofen in pregnancy is dangerous",
                                "source_section_type": "pregnancy",
                                "source_id": "IBUPROFEN :: pregnancy :: ibu-set-id",
                                "evidence_snippet": "Avoid during third trimester",
                            },
                        ]
                    },
                    "think": "Now classifying severity",
                },
                {
                    "name": "summarize_evidence",
                    "arguments": {
                        "findings": [
                            {
                                "claim": "Ibuprofen in pregnancy is dangerous",
                                "source_id": "IBUPROFEN :: pregnancy :: ibu-set-id",
                                "evidence_snippet": "Avoid during third trimester",
                                "severity": "MAJOR",
                                "source_section_type": "pregnancy",
                            },
                            {
                                "claim": "Warfarin + aspirin increases bleeding risk",
                                "source_id": "WARFARIN :: drug_interactions :: e98a2d84",
                                "evidence_snippet": "aspirin increases bleeding risk",
                                "severity": "MAJOR",
                                "source_section_type": "drug_interactions",
                            },
                        ]
                    },
                    "think": "Summarizing all evidence",
                },
                {"content": "Final report with all findings summarized."},
            ]
        )

        run_react_loop(
            query="warfarin + aspirin + ibuprofen, patient is 32 weeks pregnant",
            toolkit=toolkit,
            llm_client=llm_client,
        )

        # Verify all five tools were called
        assert toolkit.lookup_interactions.call_count >= 3, "Expected at least 3 lookup_interactions calls"
        assert toolkit.lookup_population_warnings.call_count >= 1, "Expected at least 1 lookup_population_warnings call"
        assert toolkit.search_drug_kb.call_count >= 1, "Expected at least 1 search_drug_kb call"
        assert toolkit.flag_severity.call_count >= 1, "Expected at least 1 flag_severity call"
        assert toolkit.summarize_evidence.call_count >= 1, "Expected at least 1 summarize_evidence call"

    def test_trace_log_has_think_act_observe(self) -> None:
        """The trace log contains Think / Act / Observe entries."""
        from workshop.src.react_loop import run_react_loop

        toolkit = _make_mock_toolkit()
        llm_client = _make_scripted_llm_client(
            [
                {
                    "name": "lookup_interactions",
                    "arguments": {"drug_name": "warfarin"},
                    "think": "I need to check warfarin interactions",
                },
                {"content": "Done."},
            ]
        )

        result = run_react_loop(
            query="warfarin interactions",
            toolkit=toolkit,
            llm_client=llm_client,
        )

        trace = result.get("trace", [])
        assert len(trace) >= 1, "Expected at least one trace entry"

        # Each trace entry should have think, act, observe
        entry = trace[0]
        assert "think" in entry, "Trace entry missing 'think'"
        assert "act" in entry, "Trace entry missing 'act'"
        assert "observe" in entry, "Trace entry missing 'observe'"

    def test_final_output_structure(self) -> None:
        """The final output has the expected structure."""
        from workshop.src.react_loop import run_react_loop

        toolkit = _make_mock_toolkit()
        llm_client = _make_scripted_llm_client(
            [
                {"name": "lookup_interactions", "arguments": {"drug_name": "warfarin"}, "think": "Checking warfarin"},
                {"content": "Analysis complete."},
            ]
        )

        result = run_react_loop(
            query="warfarin interactions",
            toolkit=toolkit,
            llm_client=llm_client,
        )

        assert "trace" in result
        assert "final_response" in result
        assert isinstance(result["trace"], list)

    def test_max_iterations_prevents_infinite_loop(self) -> None:
        """The loop terminates after max_iterations even if the LLM keeps calling tools."""
        from workshop.src.react_loop import run_react_loop

        toolkit = _make_mock_toolkit()

        # Create a long sequence of tool calls that exceeds max_iterations
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

        # Should have terminated at max_iterations
        assert len(result["trace"]) <= 5
