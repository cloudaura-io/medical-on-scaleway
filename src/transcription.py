"""
Audio transcription via Voxtral on Scaleway Generative APIs.

Provides a blocking helper, a streaming generator suitable
for server-sent events (SSE), and a diarized transcription
function using Voxtral's chat completions API.
"""

from __future__ import annotations

import base64
import json
import logging
from pathlib import Path
from typing import Generator

import httpx

from src.config import get_generative_client, STT_MODEL, _require

logger = logging.getLogger(__name__)


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
    logger.info(
        "transcribe_audio called, audio_path=%s",
        audio_path,
    )
    client = get_generative_client()
    path = Path(audio_path)

    with open(path, "rb") as audio_file:
        response = client.audio.transcriptions.create(
            model=STT_MODEL,
            file=audio_file,
        )

    logger.info(
        "transcribe_audio completed, text_length=%d chars",
        len(response.text),
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
    logger.info(
        "transcribe_audio_stream called, audio_path=%s",
        audio_path,
    )
    base_url = _require("SCW_GENERATIVE_API_URL")
    api_key = _require("SCW_SECRET_KEY")
    url = f"{base_url}/audio/transcriptions"
    path = Path(audio_path)

    chunk_count = 0
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
                    if chunk.get("type") != "transcript.text.delta":
                        continue
                    text = chunk.get("delta", "")
                    if text:
                        chunk_count += 1
                        yield text
                except json.JSONDecodeError:
                    logger.warning(
                        "Failed to parse streaming chunk: %s",
                        payload[:100],
                    )
                    continue

    logger.info(
        "transcribe_audio_stream completed, chunks_yielded=%d",
        chunk_count,
    )


# ---------------------------------------------------------------------------
# Diarized transcription (chat completions with audio)
# ---------------------------------------------------------------------------

_DIARIZATION_MODEL = "voxtral-small-24b-2507"

_DIARIZATION_PROMPT = (
    "Transcribe the following audio recording of a doctor-patient conversation. "
    "Label each speaker's turns with 'Doctor:' or 'Patient:' at the start of "
    "each new speaker turn. Preserve the original language of the conversation. "
    "Do not add any commentary or summary — output only the diarized transcript."
)


def transcribe_audio_diarized(audio_path: str) -> str:
    """Transcribe audio with speaker diarization via chat completions.

    Sends the audio as a base64-encoded ``input_audio`` content part
    to Voxtral's chat completions endpoint with a prompt that
    instructs the model to label speakers as Doctor and Patient.

    Parameters
    ----------
    audio_path:
        Path to a local audio file (wav, mp3, ogg, etc.).

    Returns
    -------
    str
        The diarized transcription text with speaker labels.
    """
    logger.info(
        "transcribe_audio_diarized called, audio_path=%s",
        audio_path,
    )
    client = get_generative_client()
    path = Path(audio_path)

    with open(path, "rb") as audio_file:
        audio_bytes = audio_file.read()

    audio_b64 = base64.b64encode(audio_bytes).decode()

    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": _DIARIZATION_PROMPT,
                },
                {
                    "type": "input_audio",
                    "input_audio": {
                        "data": audio_b64,
                        "format": "wav",
                    },
                },
            ],
        },
    ]

    response = client.chat.completions.create(
        model=_DIARIZATION_MODEL,
        messages=messages,
    )

    text = response.choices[0].message.content
    logger.info(
        "transcribe_audio_diarized completed, text_length=%d chars",
        len(text),
    )
    return text
