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

# ---------------------------------------------------------------------------
# Project path setup — must happen before any `src.*` import
# ---------------------------------------------------------------------------
import sys

_project_root = str(Path(__file__).resolve().parents[1])
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from src.logging_config import configure_logging
from src.transcription import transcribe_audio_diarized
from src.extraction import extract_clinical_note
from src.config import STT_MODEL, validate_config
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
    """Transcribe uploaded audio with speaker diarization via Voxtral chat completions."""
    suffix = Path(file.filename).suffix if file.filename else ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        text = transcribe_audio_diarized(tmp_path)
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    return {"transcript": text}



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
