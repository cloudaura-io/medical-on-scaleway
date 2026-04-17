"""ReAct (Think -> Act -> Observe) agent loop for drug interaction analysis.

The agent uses Mistral Small 3.2 with tool-calling to iteratively gather
evidence from the drug label knowledge base, classify severity, and
produce a grounded report with full source attribution.

Each iteration:
1. Think: model reasons about what information is still missing.
2. Act: model calls one of the five tools.
3. Observe: tool result is appended to the conversation.
4. Agent terminates when it has enough evidence and emits a final report.

Adapted from workshop/src/react_loop.py for the Drug Interactions showcase.
Uses src.drug_tools instead of workshop.src.tools.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from typing import Any

from src.drug_tools import TOOL_DEFINITIONS

logger = logging.getLogger(__name__)

DEFAULT_MAX_ITERATIONS = 15

SYSTEM_PROMPT = """You are a medical AI agent that analyzes drug interactions and population-specific warnings.
You have access to a knowledge base of FDA-approved drug labels (Structured Product Labeling, SPL).

For each medication list you receive, you MUST complete all of the following steps in order:
1. Look up drug interactions for EACH drug using lookup_interactions (one call per drug).
2. If the patient has specific population attributes (pregnancy, pediatric, geriatric, renal, hepatic), look up relevant population warnings using lookup_population_warnings.
3. Use search_drug_kb if you need broader context or are unsure which drug/section to look in.
4. Call flag_severity with the full list of findings to classify and order them.
5. Call summarize_evidence with the severity-flagged findings to produce the final structured JSON report. This step is MANDATORY - do not emit a final answer without calling summarize_evidence first.

Every claim must cite a specific FDA label section via source_id in the format:
<drug_name> :: <section_type> :: <citation_id>

where <citation_id> is the non-empty set_id if present, otherwise the application_number. Never leave the third segment empty.

Every evidence_snippet must be copied VERBATIM from a single tool observation whose metadata matches source_id. Do not paraphrase, summarize, or combine text across different observations.

Think carefully at each step about what information you still need before making the next tool call. Do not emit your final narrative response until both flag_severity and summarize_evidence have been called."""


def _dispatch_tool_call(
    toolkit: Any,
    tool_name: str,
    arguments: dict[str, Any],
) -> Any:
    """Dispatch a tool call to the appropriate toolkit method.

    Args:
        toolkit: The ToolKit instance.
        tool_name: Name of the tool to call.
        arguments: Arguments dict for the tool.

    Returns:
        The tool's return value.

    Raises:
        ValueError: If the tool name is unknown.
    """
    if tool_name == "search_drug_kb":
        return toolkit.search_drug_kb(
            query=arguments["query"],
            top_k=arguments.get("top_k", 5),
        )
    elif tool_name == "lookup_interactions":
        return toolkit.lookup_interactions(drug_name=arguments["drug_name"])
    elif tool_name == "lookup_population_warnings":
        return toolkit.lookup_population_warnings(
            drug_name=arguments["drug_name"],
            population=arguments["population"],
        )
    elif tool_name == "flag_severity":
        return toolkit.flag_severity(findings=arguments["findings"])
    elif tool_name == "summarize_evidence":
        return toolkit.summarize_evidence(findings=arguments["findings"])
    else:
        raise ValueError(f"Unknown tool: {tool_name}")


def run_react_loop_events(
    query: str,
    toolkit: Any,
    llm_client: Any,
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
    model: str = "mistral-small-3.2-24b-instruct-2506",
) -> Iterator[tuple[str, Any]]:
    """Run the ReAct loop as a generator that yields events as they happen.

    Yields tuples of (event_type, payload):
        - ("trace", {think, act, observe, tool_name, tool_result}) after each
          tool execution. `tool_result` is the raw Python value returned by the
          tool (not JSON-stringified), so callers can inspect structured output
          such as summarize_evidence findings.
        - ("final", final_text) when the agent emits a final answer without
          calling more tools, OR when max_iterations is reached.

    The loop remains synchronous because the underlying LLM/tool calls are
    blocking network I/O; yielding between them gives the consumer a chance to
    flush SSE frames to the browser before the next blocking call.
    """
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": query},
    ]

    for iteration in range(max_iterations):
        logger.info("ReAct iteration %d/%d", iteration + 1, max_iterations)

        response = llm_client.chat.completions.create(
            model=model,
            messages=messages,
            tools=TOOL_DEFINITIONS,
            temperature=0.0,
        )

        choice = response.choices[0]
        assistant_message = choice.message

        if not assistant_message.tool_calls:
            final_text = assistant_message.content or ""
            logger.info("Agent finished after %d iterations", iteration + 1)
            yield ("final", final_text)
            return

        assistant_msg: dict[str, Any] = {"role": "assistant", "content": assistant_message.content or ""}
        assistant_msg["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            }
            for tc in assistant_message.tool_calls
        ]
        messages.append(assistant_msg)

        for tool_call in assistant_message.tool_calls:
            tool_name = tool_call.function.name
            try:
                arguments = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                arguments = {}

            think_text = assistant_message.content or ""

            logger.info("  Act: %s(%s)", tool_name, json.dumps(arguments)[:100])

            try:
                result = _dispatch_tool_call(toolkit, tool_name, arguments)
            except Exception as e:
                logger.error("Tool %s failed: %s", tool_name, e)
                result = {"error": str(e)}

            observe_text = json.dumps(result, default=str)
            if len(observe_text) > 2000:
                observe_text_truncated = observe_text[:2000] + "... (truncated)"
            else:
                observe_text_truncated = observe_text

            trace_entry = {
                "think": think_text,
                "act": f"{tool_name}({json.dumps(arguments)})",
                "observe": observe_text_truncated,
                "tool_name": tool_name,
                "tool_result": result,
            }

            logger.info("  Observe: %s chars", len(observe_text))

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": observe_text_truncated,
                }
            )

            yield ("trace", trace_entry)

    logger.warning("Max iterations (%d) reached, returning partial results", max_iterations)
    yield ("final", "Max iterations reached. Returning partial analysis.")


def run_react_loop(
    query: str,
    toolkit: Any,
    llm_client: Any,
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
    model: str = "mistral-small-3.2-24b-instruct-2506",
) -> dict[str, Any]:
    """Run the ReAct agent loop and return the full result as a dict.

    Thin wrapper around run_react_loop_events for callers that don't need
    streaming (tests, notebooks).

    Returns:
        Dict with 'trace', 'final_response', and 'tool_results'.
    """
    trace: list[dict[str, Any]] = []
    tool_results: list[Any] = []
    final_response = ""

    for event_type, payload in run_react_loop_events(
        query=query,
        toolkit=toolkit,
        llm_client=llm_client,
        max_iterations=max_iterations,
        model=model,
    ):
        if event_type == "trace":
            tool_results.append(payload["tool_result"])
            trace.append(
                {
                    "think": payload["think"],
                    "act": payload["act"],
                    "observe": payload["observe"],
                }
            )
        elif event_type == "final":
            final_response = payload

    return {
        "trace": trace,
        "final_response": final_response,
        "tool_results": tool_results,
    }
