"""
Showcase 3 — Cross-domain Medical Research Agent
=================================================

FastAPI backend that:
  1. Accepts natural-language medical queries
  2. Runs a tool-calling agent loop across multiple knowledge domains
  3. Streams structured steps via SSE (thinking -> tool calls -> synthesis -> verification)

Requires Scaleway API keys and a pgvector knowledge base (see src/config.py).

Run:
    uvicorn main:app --reload --port 8002
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path

from fastapi import Request
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

# ---------------------------------------------------------------------------
# Project path setup — must happen before any `src.*` import
# ---------------------------------------------------------------------------
import sys

_project_root = str(Path(__file__).resolve().parents[1])
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from src.agent import run_agent, ALL_TOOLS
from src.rag import search as rag_search
from src.config import CHAT_MODEL, validate_config
from src.verification import verify_claims
from src.app_factory import (
    create_app,
    mount_static,
    create_index_route,
    create_health_endpoint,
)

# ---------------------------------------------------------------------------
# Validate configuration upfront
# ---------------------------------------------------------------------------
validate_config(required_vars=[
    "SCW_GENERATIVE_API_URL",
    "SCW_SECRET_KEY",
    "SCW_INFERENCE_ENDPOINT",
    "DATABASE_URL",
])

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Knowledge domains
# ---------------------------------------------------------------------------

KNOWLEDGE_DOMAINS = [
    {
        "name": "Pharmacology",
        "description": (
            "Drug interactions, mechanisms of action, "
            "pharmacokinetics, and adverse effects"
        ),
        "chunks": 45,
    },
    {
        "name": "Cardiology",
        "description": (
            "Cardiac conditions, antiarrhythmic protocols, "
            "heart failure management"
        ),
        "chunks": 38,
    },
    {
        "name": "Clinical Trials",
        "description": (
            "Published trial data, endpoints, "
            "inclusion/exclusion criteria, outcomes"
        ),
        "chunks": 27,
    },
]

SAMPLE_QUERIES = [
    (
        "Patient on empagliflozin for diabetes. "
        "Cardiologist wants to start amiodarone. Any concerns?"
    ),
    (
        "Compare statin options for a diabetic patient "
        "with elevated LDL and mild liver enzyme elevation"
    ),
    (
        "What monitoring is needed when initiating amiodarone "
        "in an elderly patient with diabetes?"
    ),
]

# ---------------------------------------------------------------------------
# Tool handlers for the agent
# ---------------------------------------------------------------------------


def _handle_search_medical_knowledge(
    query: str, domain: str | None = None
) -> list[dict]:
    """Search the RAG knowledge base."""
    logger.info(
        "_handle_search_medical_knowledge called, "
        "query=%r, domain=%s",
        query[:80],
        domain,
    )
    results = rag_search(query, top_k=5, domain=domain)
    logger.info(
        "_handle_search_medical_knowledge completed, results=%d",
        len(results),
    )
    return results


def _handle_check_drug_interactions(
    drug1: str, drug2: str
) -> dict:
    """Check drug interactions via knowledge base search."""
    logger.info(
        "_handle_check_drug_interactions called, "
        "drug1=%s, drug2=%s",
        drug1,
        drug2,
    )
    results = rag_search(
        f"{drug1} {drug2} drug interaction",
        top_k=3,
        domain="pharmacology",
    )
    if results:
        logger.info(
            "Drug interaction evidence found, sources=%d",
            len(results[:3]),
        )
        return {
            "drug1": drug1,
            "drug2": drug2,
            "evidence": [r["content"] for r in results[:3]],
            "sources": [r["source"] for r in results[:3]],
        }
    logger.warning(
        "No drug interaction evidence found for %s + %s",
        drug1,
        drug2,
    )
    return {
        "drug1": drug1,
        "drug2": drug2,
        "evidence": [],
        "sources": [],
    }


TOOL_HANDLERS = {
    "search_medical_knowledge": _handle_search_medical_knowledge,
    "check_drug_interactions": _handle_check_drug_interactions,
}

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

STATIC_DIR = Path(__file__).parent / "static"

app = create_app(title="Showcase 3 — Research Agent", version="0.1.0")
mount_static(app, STATIC_DIR)
create_index_route(app, STATIC_DIR)
create_health_endpoint(
    app,
    model=CHAT_MODEL,
    domains=lambda: len(KNOWLEDGE_DOMAINS),
)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.post("/api/research")
async def research(request: Request):
    """Run the live research agent and stream steps via SSE."""
    body = await request.json()
    query = body.get("query", "")
    if not query:
        logger.warning("Research request received with empty query")
        return JSONResponse(
            {"error": "query is required"}, status_code=400
        )

    logger.info("Research request received, query=%r", query[:120])

    async def event_generator():
        step_count = 0
        t0 = time.perf_counter()
        try:
            for step in run_agent(
                query,
                tool_handlers=TOOL_HANDLERS,
                tools=ALL_TOOLS,
            ):
                if (
                    step.get("type") == "final"
                    and isinstance(step.get("data"), str)
                ):
                    logger.info(
                        "Running Chain-of-Verification on "
                        "final response"
                    )
                    findings = []
                    try:
                        findings = verify_claims(
                            step["data"],
                            search_fn=lambda q: rag_search(
                                q, top_k=3
                            ),
                        )
                        logger.info(
                            "CoVe completed, findings=%d",
                            len(findings),
                        )
                    except Exception as exc:
                        logger.error(
                            "CoVe verification failed: %s",
                            exc,
                            exc_info=True,
                        )
                        findings = [{
                            "claim": "Verification failed",
                            "status": "NO_EVIDENCE",
                            "explanation": str(exc),
                            "evidence": "",
                            "source": None,
                        }]
                    step_count += 1
                    logger.debug(
                        "SSE event #%d, type=verification, "
                        "findings=%d",
                        step_count,
                        len(findings),
                    )
                    yield {
                        "event": "step",
                        "data": json.dumps({
                            "type": "verification",
                            "data": {"findings": findings},
                        }),
                    }
                    await asyncio.sleep(0.05)

                step_count += 1
                logger.debug(
                    "SSE event #%d, type=%s",
                    step_count,
                    step.get("type"),
                )
                yield {
                    "event": "step",
                    "data": json.dumps(step),
                }
                await asyncio.sleep(0.05)
        except Exception as exc:
            logger.error(
                "Agent raised exception for query=%r: %s",
                query[:80],
                exc,
                exc_info=True,
            )
            yield {
                "event": "step",
                "data": json.dumps({
                    "type": "final",
                    "data": {"error": str(exc)},
                }),
            }
        elapsed = time.perf_counter() - t0
        logger.info(
            "Research stream completed, steps=%d, elapsed=%.2fs",
            step_count,
            elapsed,
        )

    return EventSourceResponse(event_generator())


@app.get("/api/domains")
async def domains():
    """Return the list of knowledge domains."""
    logger.debug(
        "Serving domains, count=%d", len(KNOWLEDGE_DOMAINS)
    )
    return JSONResponse(KNOWLEDGE_DOMAINS)


@app.get("/api/sample-queries")
async def sample_queries():
    """Return sample queries for the UI."""
    logger.debug(
        "Serving sample queries, count=%d", len(SAMPLE_QUERIES)
    )
    return JSONResponse(SAMPLE_QUERIES)
