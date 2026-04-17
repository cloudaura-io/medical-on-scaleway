"""ReAct (Think -> Act -> Observe) agent loop for drug interaction analysis.

The agent uses Mistral Small 3.2 with tool-calling to iteratively gather
evidence from the drug label knowledge base, classify severity, and
produce a grounded report with full source attribution.

Each iteration:
1. Think: model reasons about what information is still missing.
2. Act: model calls one of the five tools.
3. Observe: tool result is appended to the conversation.
4. Agent terminates when it has enough evidence and emits a final report.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from workshop.src.tools import TOOL_DEFINITIONS

logger = logging.getLogger(__name__)

DEFAULT_MAX_ITERATIONS = 15

SYSTEM_PROMPT = """You are a medical AI agent that analyzes drug interactions and population-specific warnings.
You have access to a knowledge base of FDA-approved drug labels (Structured Product Labeling, SPL).

For each medication list you receive, you must:
1. Look up drug interactions for EACH drug using lookup_interactions (one call per drug).
2. If the patient has specific population attributes (pregnancy, pediatric, geriatric, renal, hepatic), look up relevant population warnings using lookup_population_warnings.
3. Use search_drug_kb if you need broader context or are unsure which drug/section to look in.
4. Once you have gathered all relevant evidence, use flag_severity to classify and order findings.
5. Finally, use summarize_evidence to produce the final structured report.

Every claim must cite a specific FDA label section via source_id in the format:
<drug_name> :: <section_type> :: <set_id>

Think carefully at each step about what information you still need before making the next tool call."""


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


def run_react_loop(
    query: str,
    toolkit: Any,
    llm_client: Any,
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
    model: str = "mistral-small-3.2-24b-instruct-2506",
) -> dict[str, Any]:
    """Run the ReAct agent loop for a drug interaction query.

    Args:
        query: The user's query (e.g., "warfarin + aspirin + ibuprofen,
            patient is 32 weeks pregnant").
        toolkit: A ToolKit instance with all five tools.
        llm_client: An OpenAI-compatible chat client.
        max_iterations: Maximum number of Think-Act-Observe iterations.
        model: The model identifier to use.

    Returns:
        Dict with:
            - 'trace': list of {think, act, observe} dicts
            - 'final_response': the model's final text response
            - 'tool_results': accumulated tool results
    """
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": query},
    ]

    trace: list[dict[str, Any]] = []
    tool_results: list[Any] = []

    for iteration in range(max_iterations):
        logger.info("ReAct iteration %d/%d", iteration + 1, max_iterations)

        # Call the LLM
        response = llm_client.chat.completions.create(
            model=model,
            messages=messages,
            tools=TOOL_DEFINITIONS,
            temperature=0.0,
        )

        choice = response.choices[0]
        assistant_message = choice.message

        # Check if the model wants to call tools
        if not assistant_message.tool_calls:
            # Model is done - return final response
            final_text = assistant_message.content or ""
            logger.info("Agent finished after %d iterations", iteration + 1)
            return {
                "trace": trace,
                "final_response": final_text,
                "tool_results": tool_results,
            }

        # Process each tool call
        # Build the assistant message for the conversation
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

            # Execute the tool
            try:
                result = _dispatch_tool_call(toolkit, tool_name, arguments)
            except Exception as e:
                logger.error("Tool %s failed: %s", tool_name, e)
                result = {"error": str(e)}

            tool_results.append(result)

            # Format the observation
            observe_text = json.dumps(result, default=str)
            if len(observe_text) > 2000:
                observe_text = observe_text[:2000] + "... (truncated)"

            # Record trace entry
            trace_entry = {
                "think": think_text,
                "act": f"{tool_name}({json.dumps(arguments)})",
                "observe": observe_text,
            }
            trace.append(trace_entry)

            logger.info("  Observe: %s chars", len(observe_text))

            # Add tool result to messages
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": observe_text,
                }
            )

    # Max iterations reached
    logger.warning("Max iterations (%d) reached, returning partial results", max_iterations)
    return {
        "trace": trace,
        "final_response": "Max iterations reached. Returning partial analysis.",
        "tool_results": tool_results,
    }
