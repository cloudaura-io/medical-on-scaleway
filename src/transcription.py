"""
Audio transcription via Voxtral on Scaleway Generative APIs.

Provides both a blocking helper and a streaming generator suitable
for server-sent events (SSE).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Generator

import httpx

from src.config import get_generative_client, STT_MODEL, _require


# ---------------------------------------------------------------------------
# Blocking transcription
# ---------------------------------------------------------------------------

def transcribe_audio(audio_path: str) -> str:
    """Transcribe an audio file and return the full text.

    Parameters
    ----------
    audio_path:
        Path to a local audio file (wav, mp3, ogg, etc.).

    Returns
    -------
    str
        The transcription text produced by Voxtral.
    """
    client = get_generative_client()
    path = Path(audio_path)

    with open(path, "rb") as audio_file:
        response = client.audio.transcriptions.create(
            model=STT_MODEL,
            file=audio_file,
        )

    return response.text


# ---------------------------------------------------------------------------
# Streaming transcription (SSE chunks)
# ---------------------------------------------------------------------------

def transcribe_audio_stream(audio_path: str) -> Generator[str, None, None]:
    """Stream transcription chunks via the Scaleway Generative APIs SSE endpoint.

    Yields incremental text chunks as they arrive from the server.  The
    caller can forward these directly over an SSE connection.

    Parameters
    ----------
    audio_path:
        Path to a local audio file.

    Yields
    ------
    str
        Successive text fragments of the transcription.
    """
    base_url = _require("SCW_GENERATIVE_API_URL")
    api_key = _require("SCW_SECRET_KEY")
    url = f"{base_url}/audio/transcriptions"
    path = Path(audio_path)

    with open(path, "rb") as audio_file:
        files = {"file": (path.name, audio_file, "application/octet-stream")}
        data = {"model": STT_MODEL, "stream": "true"}
        headers = {"Authorization": f"Bearer {api_key}"}

        with httpx.stream(
            "POST", url, files=files, data=data, headers=headers, timeout=300.0
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line or not line.startswith("data: "):
                    continue
                payload = line[len("data: "):]
                if payload.strip() == "[DONE]":
                    break
                try:
                    chunk = json.loads(payload)
                    text = chunk.get("text", "")
                    if text:
                        yield text
                except json.JSONDecodeError:
                    continue
