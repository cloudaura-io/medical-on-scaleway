"""
Showcase 1 — Doctor's Ambient Scribe
=====================================

FastAPI backend that:
  1. Accepts audio uploads and transcribes via Voxtral (Scaleway Generative APIs)
  2. Extracts structured clinical notes from the transcript via Mistral

Run:
    uvicorn main:app --reload --port 8000
"""

from __future__ import annotations

import time
import tempfile
from pathlib import Path

from fastapi import File, UploadFile, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import iterate_in_threadpool

# ---------------------------------------------------------------------------
# Project path setup — must happen before any `src.*` import
# ---------------------------------------------------------------------------
import sys

_project_root = str(Path(__file__).resolve().parents[1])
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from starlette.responses import StreamingResponse

from src.logging_config import configure_logging
from src.transcription import transcribe_audio, transcribe_audio_stream
from src.extraction import extract_clinical_note
from src.config import STT_MODEL, validate_config
from src.sse_utils import format_sse_event, safe_streaming_wrapper
from src.app_factory import (
    create_app,
    mount_static,
    create_index_route,
    create_health_endpoint,
)

# ---------------------------------------------------------------------------
# Logging — must be configured before anything else logs
# ---------------------------------------------------------------------------
configure_logging()

# ---------------------------------------------------------------------------
# Validate configuration upfront
# ---------------------------------------------------------------------------
validate_config(required_vars=[
    "SCW_GENERATIVE_API_URL",
    "SCW_SECRET_KEY",
])

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

STATIC_DIR = Path(__file__).parent / "static"
SHARED_STATIC_DIR = Path(__file__).resolve().parents[1] / "static" / "shared"

app = create_app(
    title="Ambient Scribe — Scaleway Medical AI Lab",
    version="1.0.0",
)

# Mount the shared static directory BEFORE the app-specific one so
# the more-specific /static/shared path is matched first.
from fastapi.staticfiles import StaticFiles

app.mount(
    "/static/shared",
    StaticFiles(directory=str(SHARED_STATIC_DIR)),
    name="shared_static",
)
mount_static(app, STATIC_DIR)

create_index_route(app, STATIC_DIR)
create_health_endpoint(app, model=STT_MODEL)

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


# -- Transcription ----------------------------------------------------------


@app.post("/api/transcribe")
async def transcribe(file: UploadFile = File(...)):
    """Transcribe uploaded audio via Voxtral on Scaleway Generative APIs."""
    suffix = Path(file.filename).suffix if file.filename else ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        text = transcribe_audio(tmp_path)
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    return {"transcript": text}


# -- Streaming Transcription (SSE) -----------------------------------------


@app.post("/api/transcribe-stream")
async def transcribe_stream(file: UploadFile = File(...)):
    """Stream transcription via SSE as chunks arrive from Voxtral.

    Emits ``transcript_chunk`` events with incremental text and a
    final ``transcript_done`` event when the stream is exhausted.
    """
    suffix = Path(file.filename).suffix if file.filename else ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    async def _generate():
        try:
            async for chunk in iterate_in_threadpool(transcribe_audio_stream(tmp_path)):
                yield format_sse_event("transcript_chunk", {"text": chunk})
            yield format_sse_event("transcript_done", {})
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    return StreamingResponse(
        safe_streaming_wrapper(_generate()),
        media_type="text/event-stream",
    )


# -- Extraction -------------------------------------------------------------


@app.post("/api/extract")
async def extract(request: Request):
    """Extract a structured clinical note from a transcript."""
    body = await request.json()
    transcript = body.get("transcript", "")
    if not transcript:
        return JSONResponse(
            {"error": "transcript field is required"},
            status_code=400,
        )

    start = time.perf_counter()
    result = extract_clinical_note(transcript)
    elapsed = round(time.perf_counter() - start, 2)

    return {"clinical_note": result, "processing_time_s": elapsed}
