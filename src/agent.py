"""
Tool-calling agent loop using OpenAI-compatible function calling.

No LangGraph — a plain Python loop that yields structured steps,
ready for SSE streaming.
"""

from __future__ import annotations

import json
from typing import Any, Callable, Generator

from src.config import get_generative_client, CHAT_MODEL

# ---------------------------------------------------------------------------
# Built-in tool definitions (OpenAI function-calling format)
# ---------------------------------------------------------------------------

TOOL_SEARCH_MEDICAL_KNOWLEDGE = {
    "type": "function",
    "function": {
        "name": "search_medical_knowledge",
        "description": (
            "Search the medical knowledge base for information relevant to a query. "
            "Returns ranked text chunks with source metadata."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural-language search query.",
                },
                "domain": {
                    "type": "string",
                    "description": "Optional domain filter (e.g., pharmacology, oncology).",
                },
            },
            "required": ["query"],
        },
    },
}

TOOL_CHECK_DRUG_INTERACTIONS = {
    "type": "function",
    "function": {
        "name": "check_drug_interactions",
        "description": (
            "Check for known interactions between two medications. "
            "Returns severity level and clinical recommendation."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "drug1": {
                    "type": "string",
                    "description": "First drug name (generic).",
                },
                "drug2": {
                    "type": "string",
                    "description": "Second drug name (generic).",
                },
            },
            "required": ["drug1", "drug2"],
        },
    },
}

TOOL_EXTRACT_PATIENT_DATA = {
    "type": "function",
    "function": {
        "name": "extract_patient_data",
        "description": (
            "Extract structured clinical data from free-text patient notes "
            "or transcripts."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Free-text clinical note or transcript.",
                },
            },
            "required": ["text"],
        },
    },
}

# Convenience list of all built-in tools.
ALL_TOOLS = [
    TOOL_SEARCH_MEDICAL_KNOWLEDGE,
    TOOL_CHECK_DRUG_INTERACTIONS,
    TOOL_EXTRACT_PATIENT_DATA,
]

# ---------------------------------------------------------------------------
# Agent system prompt
# ---------------------------------------------------------------------------

_AGENT_SYSTEM_PROMPT = """\
You are a medical AI research assistant.  You have access to tools that
let you search a curated medical knowledge base, check drug interactions,
and extract structured data from clinical text.

Guidelines:
- ALWAYS search the knowledge base before answering medical questions.
- Cite your sources using [Source: <name>] after each factual statement.
- If you are uncertain, say so — never fabricate medical information.
- For drug interactions, always use the dedicated tool.
- Think step-by-step: state your reasoning before giving a final answer.
"""

# ---------------------------------------------------------------------------
# Step types emitted by the agent loop
# ---------------------------------------------------------------------------

def _step(step_type: str, data: Any) -> dict:
    return {"type": step_type, "data": data}


# ---------------------------------------------------------------------------
# Agent loop
# ---------------------------------------------------------------------------

def run_agent(
    query: str,
    tool_handlers: dict[str, Callable[..., Any]],
    tools: list[dict] | None = None,
    max_iterations: int = 10,
) -> Generator[dict, None, None]:
    """Execute a tool-calling agent loop, yielding steps for SSE streaming.

    Parameters
    ----------
    query:
        The user's question or instruction.
    tool_handlers:
        Mapping of function name -> callable that executes the tool.
        Each callable receives keyword arguments matching the function
        parameters and returns a JSON-serialisable result.
    tools:
        OpenAI-format tool definitions.  Defaults to :data:`ALL_TOOLS`.
    max_iterations:
        Safety limit on the number of LLM round-trips.

    Yields
    ------
    dict
        Steps of the form ``{"type": <step_type>, "data": <payload>}`` where
        *step_type* is one of:

        - ``thinking``    — the model's chain-of-thought reasoning
        - ``tool_call``   — a tool invocation request
        - ``tool_result`` — the result returned by the tool handler
        - ``synthesis``   — intermediate synthesis after tool results
        - ``verification``— optional self-check before final answer
        - ``final``       — the completed response
    """
    if tools is None:
        tools = ALL_TOOLS

    client = get_generative_client()
    messages: list[dict] = [
        {"role": "system", "content": _AGENT_SYSTEM_PROMPT},
        {"role": "user", "content": query},
    ]

    yield _step("thinking", "Analysing the query and deciding which tools to use...")

    for _iteration in range(max_iterations):
        response = client.chat.completions.create(
            model=CHAT_MODEL,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            temperature=0.2,
        )

        choice = response.choices[0]
        message = choice.message

        # ---- No tool calls → we have a final (or synthesis) answer --------
        if not message.tool_calls:
            content = message.content or ""
            messages.append({"role": "assistant", "content": content})
            yield _step("final", content)
            return

        # ---- Process tool calls -------------------------------------------
        # Append the assistant message with tool_calls first.
        messages.append(message.model_dump())

        for tc in message.tool_calls:
            fn_name = tc.function.name
            try:
                fn_args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                fn_args = {}

            yield _step("tool_call", {"name": fn_name, "arguments": fn_args})

            handler = tool_handlers.get(fn_name)
            if handler is None:
                result = {"error": f"Unknown tool: {fn_name}"}
            else:
                try:
                    result = handler(**fn_args)
                except Exception as exc:
                    result = {"error": str(exc)}

            result_str = json.dumps(result) if not isinstance(result, str) else result

            yield _step("tool_result", {"name": fn_name, "result": result_str})

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result_str,
                }
            )

        yield _step("synthesis", "Integrating tool results...")

    # If we exhausted iterations, yield whatever we have.
    yield _step(
        "final",
        "I was unable to complete the analysis within the allowed number of steps. "
        "Please try a more specific question.",
    )
