"""
Audio transcription via Voxtral on Scaleway Generative APIs.

Provides a diarized transcription function using Voxtral's chat
completions API with speaker labeling (Doctor / Patient).
"""

from __future__ import annotations

import base64
import logging
from pathlib import Path

from src.config import get_generative_client

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Diarized transcription (chat completions with audio)
# ---------------------------------------------------------------------------

_DIARIZATION_MODEL = "voxtral-small-24b-2507"

_DIARIZATION_PROMPT = (
    "Transcribe the following audio recording of a doctor-patient conversation. "
    "Label each speaker's turns with 'Doctor:' or 'Patient:' at the start of "
    "each new speaker turn. Preserve the original language of the conversation. "
    "Do not add any commentary or summary - output only the diarized transcript."
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
