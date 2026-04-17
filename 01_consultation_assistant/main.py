"""
Showcase 1 - Doctor Assistant
==============================

FastAPI backend that:
  1. Accepts audio uploads and transcribes via Voxtral (Scaleway Generative APIs)
  2. Extracts structured clinical notes from the transcript via Mistral

Run:
    uvicorn main:app --reload --port 8000
"""

from __future__ import annotations

import contextlib
import json

# ---------------------------------------------------------------------------
# Project path setup - must happen before any `src.*` import
# ---------------------------------------------------------------------------
import sys
import tempfile
import time
from pathlib import Path

from fastapi import File, Request, UploadFile, WebSocket, WebSocketDisconnect
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
from src.config import STT_MODEL, validate_config
from src.extraction import extract_clinical_note, extract_clinical_note_stream
from src.logging_config import configure_logging
from src.sse_utils import format_sse_event, safe_streaming_wrapper
from src.transcription import transcribe_audio_diarized
from src.transcription_realtime import RealtimeTranscriber, diarize_transcript

# ---------------------------------------------------------------------------
# Logging - must be configured before anything else logs
# ---------------------------------------------------------------------------
configure_logging()

# ---------------------------------------------------------------------------
# Validate configuration upfront
# ---------------------------------------------------------------------------
validate_config(
    required_vars=[
        "SCW_GENERATIVE_API_URL",
        "SCW_SECRET_KEY",
    ]
)

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

STATIC_DIR = Path(__file__).parent / "static"
PROJECT_ROOT = Path(__file__).resolve().parents[1]

app = create_app(
    title="Doctor Assistant - Scaleway Medical AI Lab",
    version="1.0.0",
)

mount_shared_static(app, PROJECT_ROOT)
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


# -- WebSocket realtime transcription ----------------------------------------


@app.websocket("/ws/transcribe")
async def ws_transcribe(websocket: WebSocket):
    """Stream live audio via WebSocket for realtime transcription.

    Protocol:
      - Client sends binary frames (PCM16 audio chunks)
      - Client sends JSON ``{"type": "stop"}`` to signal end of audio
      - Server sends JSON ``{"type": "delta", "text": "..."}`` for each word
      - Server sends JSON ``{"type": "diarized", "text": "..."}`` after diarization
      - Server sends JSON ``{"type": "done"}`` when complete
    """
    await websocket.accept()

    transcriber = RealtimeTranscriber()
    raw_text_parts: list[str] = []

    try:
        await transcriber.connect()

        import asyncio

        # Task to receive deltas and forward to browser
        async def relay_deltas():
            async for delta in transcriber.receive_deltas():
                raw_text_parts.append(delta)
                await websocket.send_json({"type": "delta", "text": delta})

        relay_task = asyncio.create_task(relay_deltas())

        # Receive audio from browser until stop signal
        while True:
            message = await websocket.receive()

            if "bytes" in message and message["bytes"]:
                await transcriber.send_audio(message["bytes"])

            elif "text" in message and message["text"]:
                data = json.loads(message["text"])
                if data.get("type") == "stop":
                    await transcriber.finish()
                    break

        # Wait for all deltas to be relayed
        await relay_task

        # Post-process: diarize the raw transcript
        raw_text = "".join(raw_text_parts)
        if raw_text.strip():
            diarized = diarize_transcript(raw_text)
            await websocket.send_json({"type": "diarized", "text": diarized})

        await websocket.send_json({"type": "done"})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        with contextlib.suppress(Exception):
            await websocket.send_json({"type": "error", "message": str(e)})
    finally:
        await transcriber.disconnect()


# -- Extraction -------------------------------------------------------------


@app.post("/api/extract")
async def extract(request: Request):
    """Extract a structured clinical note from a transcript (non-streaming)."""
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


@app.post("/api/extract/stream")
async def extract_stream(request: Request):
    """Stream clinical-note extraction as SSE events.

    Events:
      - {"type": "token", "text": "..."} - raw chunks as the model emits them
      - {"type": "clinical_note", "data": {...}, "processing_time_s": float}
      - {"type": "error", "error": "..."}
    """
    body = await request.json()
    transcript = body.get("transcript", "")
    if not transcript:
        return JSONResponse(
            {"error": "transcript field is required"},
            status_code=400,
        )

    async def event_generator():
        import asyncio

        start = time.perf_counter()
        loop = asyncio.get_running_loop()
        iterator = extract_clinical_note_stream(transcript)

        try:
            while True:
                event = await loop.run_in_executor(None, next, iterator, None)
                if event is None:
                    break
                kind, payload = event
                if kind == "token":
                    yield format_sse_event("step", {"type": "token", "text": payload})
                elif kind == "clinical_note":
                    elapsed = round(time.perf_counter() - start, 2)
                    yield format_sse_event(
                        "step",
                        {
                            "type": "clinical_note",
                            "data": payload,
                            "processing_time_s": elapsed,
                        },
                    )
                elif kind == "error":
                    yield format_sse_event("step", {"type": "error", "error": payload})
        except Exception as exc:
            yield format_sse_event("step", {"type": "error", "error": str(exc)})

    return StreamingResponse(
        safe_streaming_wrapper(event_generator()),
        media_type="text/event-stream",
    )
