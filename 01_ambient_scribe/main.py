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
# Project path setup
# ---------------------------------------------------------------------------
from src.app_factory import setup_project_path

setup_project_path(__file__)

from src.transcription import transcribe_audio  # noqa: E402
from src.extraction import extract_clinical_note  # noqa: E402
from src.config import STT_MODEL  # noqa: E402
from src.app_factory import (  # noqa: E402
    create_app,
    mount_static,
    create_index_route,
    create_health_endpoint,
)

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

STATIC_DIR = Path(__file__).parent / "static"

app = create_app(
    title="Ambient Scribe — Scaleway Medical AI Lab",
    version="1.0.0",
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
