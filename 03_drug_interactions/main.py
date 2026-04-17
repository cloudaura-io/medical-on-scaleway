"""
Showcase 3 - Drug Interactions Checker
======================================

FastAPI backend that:
  1. Accepts a list of medications and optional population
  2. Runs a ReAct agent loop to analyze drug interactions via FDA labels
  3. Streams structured steps via SSE (think -> act -> observe -> report)

Requires Scaleway API keys and a pgvector knowledge base (see src/config.py).

Run:
    uvicorn 03_drug_interactions.main:app --reload --port 8003
"""

from __future__ import annotations

import asyncio
import logging
import sys
import time
from pathlib import Path
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse, StreamingResponse

_project_root = str(Path(__file__).resolve().parents[1])
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from src.app_factory import (
    create_app,
    create_health_endpoint,
    create_index_route,
    mount_shared_static,
    mount_static,
)
from src.config import (
    CHAT_MODEL,
    EMBEDDING_DIMENSIONS,
    EMBEDDING_MODEL,
    get_db_connection,
    get_generative_client,
    validate_config,
)
from src.drug_embeddings import EmbeddingsClient
from src.drug_react import run_react_loop_events
from src.drug_tools import ToolKit
from src.logging_config import configure_logging
from src.sse_utils import format_sse_event, safe_streaming_wrapper

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
configure_logging()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Validate configuration upfront
# ---------------------------------------------------------------------------
validate_config(
    required_vars=[
        "SCW_GENERATIVE_API_URL",
        "SCW_SECRET_KEY",
        "SCW_INFERENCE_ENDPOINT",
        "DATABASE_URL",
    ]
)

# ---------------------------------------------------------------------------
# Sample queries for the UI
# ---------------------------------------------------------------------------

SAMPLE_QUERIES: list[dict[str, Any]] = [
    {
        # SSRI + opioid -> classic serotonin syndrome + CYP2D6 interaction
        "label": "Sertraline + Tramadol",
        "medications": ["sertraline", "tramadol"],
        "population": None,
    },
    {
        # Anticoagulant + opioid -> bleeding + CNS depression risk
        "label": "Warfarin + Tramadol",
        "medications": ["warfarin", "tramadol"],
        "population": None,
    },
    {
        # Anticoagulant + SSRI -> CYP2C9 interaction increases warfarin effect
        "label": "Warfarin + Sertraline",
        "medications": ["warfarin", "sertraline"],
        "population": None,
    },
    {
        # Diabetes + ACE inhibitor -> renal function interplay
        "label": "Metformin + Lisinopril",
        "medications": ["metformin", "lisinopril"],
        "population": None,
    },
    {
        # Two oral antidiabetics in elderly -> hypoglycemia risk
        "label": "Metformin + Glipizide (Geriatric)",
        "medications": ["metformin", "glipizide"],
        "population": "geriatric",
    },
    {
        # Anticoagulant + opioid in pregnancy -> warfarin teratogenic + tramadol withdrawal
        "label": "Warfarin + Tramadol (Pregnancy)",
        "medications": ["warfarin", "tramadol"],
        "population": "pregnancy",
    },
]

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

STATIC_DIR = Path(__file__).parent / "static"
PROJECT_ROOT = Path(__file__).resolve().parents[1]

app = create_app(title="Showcase 3 - Drug Interactions", version="0.1.0")
mount_shared_static(app, PROJECT_ROOT)
mount_static(app, STATIC_DIR)
create_index_route(app, STATIC_DIR)
create_health_endpoint(app, model=CHAT_MODEL)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/api/sample-queries")
async def sample_queries():
    """Return pre-defined sample medication combinations for one-click demo."""
    logger.debug("Serving sample queries, count=%d", len(SAMPLE_QUERIES))
    return JSONResponse(SAMPLE_QUERIES)


@app.post("/api/analyze")
async def analyze(request: Request):
    """Run drug interaction analysis and stream ReAct agent steps via SSE.

    Accepts JSON body:
        {
            "medications": ["warfarin", "aspirin", ...],
            "population": "pregnancy" | "pediatric" | "geriatric" | "renal" | "hepatic" | null
        }
    """
    body = await request.json()
    medications = body.get("medications", [])
    population = body.get("population")

    if not medications:
        logger.warning("Analyze request with empty medications list")
        return JSONResponse(
            {"error": "medications list is required and must not be empty"},
            status_code=400,
        )

    # Build the query string
    med_str = " + ".join(medications)
    query = f"Analyze drug interactions for: {med_str}"
    if population:
        query += f", patient population: {population}"

    logger.info("Analyze request: medications=%s, population=%s", medications, population)

    async def event_generator():
        step_count = 0
        t0 = time.perf_counter()

        try:
            conn = get_db_connection()
            llm_client = get_generative_client()
            embeddings_client = EmbeddingsClient(
                client=llm_client,
                model=EMBEDDING_MODEL,
                dimensions=EMBEDDING_DIMENSIONS,
            )

            toolkit = ToolKit(
                conn=conn,
                embeddings_client=embeddings_client,
                llm_client=llm_client,
            )

            findings: list[dict[str, Any]] | None = None
            flagged: list[dict[str, Any]] | None = None
            raw_observations: list[dict[str, Any]] = []
            final_text = ""

            loop = asyncio.get_running_loop()
            event_iterator = run_react_loop_events(
                query=query,
                toolkit=toolkit,
                llm_client=llm_client,
            )

            # Drive the synchronous generator step-by-step via a thread so the
            # SSE response can flush each trace entry to the browser as the
            # ReAct loop produces it, rather than waiting for it to finish.
            while True:
                event = await loop.run_in_executor(None, next, event_iterator, None)
                if event is None:
                    break
                event_type, payload = event

                if event_type == "trace":
                    step_count += 1
                    trace_only = {
                        "think": payload.get("think", ""),
                        "act": payload.get("act", ""),
                        "observe": payload.get("observe", ""),
                    }
                    yield format_sse_event(
                        "step",
                        {
                            "type": "trace",
                            "data": trace_only,
                        },
                    )

                    tool_name = payload.get("tool_name")
                    tool_result = payload.get("tool_result")

                    if tool_name == "summarize_evidence" and isinstance(tool_result, list):
                        findings = tool_result
                    elif tool_name == "flag_severity" and isinstance(tool_result, list):
                        flagged = tool_result
                    elif tool_name in (
                        "lookup_interactions",
                        "lookup_population_warnings",
                        "search_drug_kb",
                    ) and isinstance(tool_result, list):
                        raw_observations.append({"tool": tool_name, "rows": tool_result})
                elif event_type == "final":
                    final_text = payload

            # If the agent never called summarize_evidence, synthesize findings
            # ourselves so the UI panel isn't empty.
            if not findings:
                findings = _synthesize_findings(
                    toolkit=toolkit,
                    flagged=flagged,
                    raw_observations=raw_observations,
                )

            if findings:
                findings = _enrich_findings(
                    findings=findings,
                    raw_observations=raw_observations,
                )
                yield format_sse_event(
                    "step",
                    {
                        "type": "findings",
                        "data": findings,
                    },
                )

            step_count += 1
            yield format_sse_event(
                "step",
                {
                    "type": "final",
                    "data": final_text,
                },
            )

        except Exception as exc:
            logger.error(
                "Analysis failed for medications=%s: %s",
                medications,
                exc,
                exc_info=True,
            )
            yield format_sse_event(
                "step",
                {
                    "type": "error",
                    "data": {"error": str(exc)},
                },
            )

        elapsed = time.perf_counter() - t0
        logger.info(
            "Analysis stream completed, steps=%d, elapsed=%.2fs",
            step_count,
            elapsed,
        )

    return StreamingResponse(
        safe_streaming_wrapper(event_generator()),
        media_type="text/event-stream",
    )


def _synthesize_findings(
    toolkit: ToolKit,
    flagged: list[dict[str, Any]] | None,
    raw_observations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build structured findings when the agent skipped summarize_evidence.

    Prefer flag_severity output if present. Otherwise derive one finding per
    label chunk pulled via lookup_* / search_drug_kb.
    """
    if flagged:
        try:
            return toolkit.summarize_evidence(findings=flagged)
        except Exception as exc:
            logger.warning("summarize_evidence fallback failed: %s", exc)
            return flagged

    draft: list[dict[str, Any]] = []
    seen_source_ids: set[str] = set()
    for entry in raw_observations:
        for row in entry.get("rows", []):
            if not isinstance(row, dict):
                continue
            drug = row.get("drug_name", "")
            section = row.get("section_type", "")
            # openFDA snapshots vary: prefer set_id, fall back to application_number
            citation_id = row.get("set_id") or row.get("application_number") or ""
            text = row.get("text", "") or ""
            if not drug or not citation_id:
                continue
            source_id = f"{drug} :: {section} :: {citation_id}"
            if source_id in seen_source_ids:
                continue
            seen_source_ids.add(source_id)
            snippet = text[:240].strip()
            # Pass through the chunker's source_url if present (it picks the
            # right openFDA query field), otherwise the frontend will derive
            # one from the citation_id.
            source_url = row.get("source_url") or ""
            draft.append(
                {
                    "claim": f"{drug}: {section.replace('_', ' ')} noted in FDA label.",
                    "source_id": source_id,
                    "source_url": source_url,
                    "evidence_snippet": snippet,
                    "source_section_type": section,
                }
            )

    if not draft:
        return []

    try:
        classified = toolkit.flag_severity(findings=draft)
        return toolkit.summarize_evidence(findings=classified)
    except Exception as exc:
        logger.warning("Fallback classification failed: %s", exc)
        return draft


def _enrich_findings(
    findings: list[dict[str, Any]],
    raw_observations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Normalize source_id, attach a clickable openFDA URL, and verify each
    evidence_snippet against the observation it cites.

    Why: summarize_evidence produces source_ids with an empty trailing
    segment when the openFDA chunk had no set_id, and occasionally emits
    evidence_snippets that are paraphrased or synthesized across sources
    (breaking the "every claim traces to one label section" guarantee).
    This pass cross-references each finding against the observations
    captured during the ReAct loop, swaps application_number in when
    set_id is blank, builds the openFDA API URL the frontend renders as a
    link, and marks verified=False (substituting a verbatim excerpt from
    the cited section) whenever the model's snippet is not actually a
    substring of that section's label text.
    """
    obs_by_key: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for entry in raw_observations:
        for row in entry.get("rows", []):
            if not isinstance(row, dict):
                continue
            drug_lc = (row.get("drug_name") or "").lower()
            section = row.get("section_type") or ""
            if not drug_lc or not section:
                continue
            obs_by_key.setdefault((drug_lc, section), []).append(row)

    def _norm(text: str) -> str:
        return " ".join((text or "").lower().split())

    enriched: list[dict[str, Any]] = []
    for finding in findings:
        if not isinstance(finding, dict):
            enriched.append(finding)
            continue

        copy = dict(finding)
        source_id = (copy.get("source_id") or "").strip()
        parts = [p.strip() for p in source_id.split("::")]
        drug = parts[0] if len(parts) > 0 else ""
        section = parts[1] if len(parts) > 1 and parts[1] else (copy.get("source_section_type") or "")
        citation_id = parts[2] if len(parts) > 2 else ""

        rows = obs_by_key.get((drug.lower(), section), [])

        snippet = copy.get("evidence_snippet") or ""
        snippet_head = _norm(snippet)[:160]

        chosen = None
        for row in rows:
            if snippet_head and snippet_head in _norm(row.get("text") or ""):
                chosen = row
                break
        if chosen is None and rows:
            chosen = rows[0]

        if chosen is not None:
            set_id = (chosen.get("set_id") or "").strip()
            app_no = (chosen.get("application_number") or "").strip()
            new_cid = set_id or app_no or citation_id
            if drug and section and new_cid:
                copy["source_id"] = f"{drug} :: {section} :: {new_cid}"

            url = (chosen.get("source_url") or "").strip()
            if not url and new_cid:
                field = "openfda.application_number" if new_cid.startswith(("ANDA", "NDA", "BLA")) else "openfda.set_id"
                url = f"https://api.fda.gov/drug/label.json?search={field}:{new_cid}"
            if url:
                copy["source_url"] = url

            text = chosen.get("text") or ""
            if snippet_head and snippet_head in _norm(text):
                copy["verified"] = True
            else:
                copy["verified"] = False
                excerpt = text.strip()[:320]
                if excerpt:
                    copy["evidence_snippet"] = excerpt
        else:
            copy.setdefault("verified", False)

        copy.setdefault("source_section_type", section)
        enriched.append(copy)

    return enriched
