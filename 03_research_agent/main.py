"""
Showcase 3 — Cross-domain Medical Research Agent
=================================================

FastAPI backend that:
  1. Accepts natural-language medical queries
  2. Runs a tool-calling agent loop across multiple knowledge domains
  3. Streams structured steps via SSE (thinking → tool calls → synthesis → verification)

Requires Scaleway API keys and a pgvector knowledge base (see src/config.py).

Run:
    uvicorn main:app --reload --port 8002
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse

# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Path fixup so `from src.…` resolves to the repo root
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agent import run_agent, ALL_TOOLS  # noqa: E402
from src.rag import search as rag_search  # noqa: E402
from src.config import CHAT_MODEL  # noqa: E402

# ---------------------------------------------------------------------------
# Knowledge domains
# ---------------------------------------------------------------------------

KNOWLEDGE_DOMAINS = [
    {
        "name": "Pharmacology",
        "description": "Drug interactions, mechanisms of action, pharmacokinetics, and adverse effects",
        "chunks": 45,
    },
    {
        "name": "Cardiology",
        "description": "Cardiac conditions, antiarrhythmic protocols, heart failure management",
        "chunks": 38,
    },
    {
        "name": "Clinical Trials",
        "description": "Published trial data, endpoints, inclusion/exclusion criteria, outcomes",
        "chunks": 27,
    },
]

SAMPLE_QUERIES = [
    "Patient on empagliflozin for diabetes. Cardiologist wants to start amiodarone. Any concerns?",
    "Compare statin options for a diabetic patient with elevated LDL and mild liver enzyme elevation",
    "What monitoring is needed when initiating amiodarone in an elderly patient with diabetes?",
]

# ---------------------------------------------------------------------------
# Tool handlers for the agent
# ---------------------------------------------------------------------------


def _handle_search_medical_knowledge(query: str, domain: str | None = None) -> list[dict]:
    """Search the RAG knowledge base."""
    logger.info("_handle_search_medical_knowledge called, query=%r, domain=%s", query[:80], domain)
    results = rag_search(query, top_k=5, domain=domain)
    logger.info("_handle_search_medical_knowledge completed, results=%d", len(results))
    return results


def _handle_check_drug_interactions(drug1: str, drug2: str) -> dict:
    """Check drug interactions via knowledge base search."""
    logger.info("_handle_check_drug_interactions called, drug1=%s, drug2=%s", drug1, drug2)
    results = rag_search(f"{drug1} {drug2} drug interaction", top_k=3, domain="pharmacology")
    if results:
        logger.info("Drug interaction evidence found, sources=%d", len(results[:3]))
        return {
            "drug1": drug1,
            "drug2": drug2,
            "evidence": [r["content"] for r in results[:3]],
            "sources": [r["source"] for r in results[:3]],
        }
    logger.warning("No drug interaction evidence found for %s + %s", drug1, drug2)
    return {"drug1": drug1, "drug2": drug2, "evidence": [], "sources": []}


TOOL_HANDLERS = {
    "search_medical_knowledge": _handle_search_medical_knowledge,
    "check_drug_interactions": _handle_check_drug_interactions,
}

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(title="Showcase 3 — Research Agent", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/", response_class=HTMLResponse)
async def root():
    index = STATIC_DIR / "index.html"
    return HTMLResponse(index.read_text())


@app.post("/api/research")
async def research(request: Request):
    """Run the live research agent and stream steps via SSE."""
    body = await request.json()
    query = body.get("query", "")
    if not query:
        return JSONResponse({"error": "query is required"}, status_code=400)

    async def event_generator():
        try:
            for step in run_agent(query, tool_handlers=TOOL_HANDLERS, tools=ALL_TOOLS):
                yield {
                    "event": "step",
                    "data": json.dumps(step),
                }
                await asyncio.sleep(0.05)  # Small pause for UI responsiveness
        except Exception as exc:
            yield {
                "event": "step",
                "data": json.dumps({"type": "final", "data": {"error": str(exc)}}),
            }

    return EventSourceResponse(event_generator())


@app.get("/api/domains")
async def domains():
    return JSONResponse(KNOWLEDGE_DOMAINS)


@app.get("/api/sample-queries")
async def sample_queries():
    return JSONResponse(SAMPLE_QUERIES)


@app.get("/api/health")
async def health():
    return JSONResponse({
        "status": "ok",
        "model": CHAT_MODEL,
        "domains": len(KNOWLEDGE_DOMAINS),
    })
