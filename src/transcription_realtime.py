"""
Realtime audio transcription via Voxtral Mini 4B on self-hosted vLLM.

Connects to the vLLM ``/v1/realtime`` WebSocket endpoint, streams PCM16
audio chunks, and yields transcription text deltas as they arrive.

Protocol (vLLM Realtime API):
  1. Client opens WebSocket -> server sends ``session.created``
  2. Client sends ``session.update`` with model name
  3. Client sends ``input_audio_buffer.commit`` (initial)
  4. Client streams ``input_audio_buffer.append`` with base64 PCM16 chunks
  5. Server streams ``transcription.delta`` with partial text
  6. Client sends ``input_audio_buffer.commit`` with ``final: true``
  7. Server sends ``transcription.done`` with complete text
"""

from __future__ import annotations

import base64
import json
import logging
from collections.abc import AsyncIterator

import websockets

from src.config import CHAT_MODEL, REALTIME_STT_MODEL, get_generative_client, get_realtime_ws_url
from src.transcription import transcribe_audio_diarized

logger = logging.getLogger(__name__)

# Size of each audio chunk sent to vLLM (bytes).  4096 bytes = 128ms at 16kHz mono PCM16.
CHUNK_SIZE = 4096


class RealtimeTranscriber:
    """Async WebSocket client for Voxtral Realtime transcription on vLLM."""

    def __init__(self) -> None:
        self._ws = None
        self._session_id: str | None = None

    async def connect(self) -> None:
        """Open a WebSocket to the vLLM realtime endpoint and initialise the session."""
        url = get_realtime_ws_url()
        logger.info("Connecting to Voxtral Realtime at %s", url)

        self._ws = await websockets.connect(url)

        # Wait for session.created
        raw = await self._ws.recv()
        msg = json.loads(raw)
        if msg.get("type") != "session.created":
            raise RuntimeError(f"Expected session.created, got: {msg}")
        self._session_id = msg.get("id")
        logger.info("Session created: %s", self._session_id)

        # Send session.update with model
        await self._ws.send(
            json.dumps(
                {
                    "type": "session.update",
                    "model": f"mistralai/{REALTIME_STT_MODEL}",
                }
            )
        )

        # Send initial commit (signals ready to receive audio)
        await self._ws.send(
            json.dumps(
                {
                    "type": "input_audio_buffer.commit",
                }
            )
        )
        logger.info("Session initialised, ready for audio")

    async def send_audio(self, chunk: bytes) -> None:
        """Send a PCM16 audio chunk (base64-encoded) to the model."""
        if self._ws is None:
            raise RuntimeError("Not connected - call connect() first")

        encoded = base64.b64encode(chunk).decode("utf-8")
        await self._ws.send(
            json.dumps(
                {
                    "type": "input_audio_buffer.append",
                    "audio": encoded,
                }
            )
        )

    async def finish(self) -> None:
        """Signal that all audio has been sent."""
        if self._ws is None:
            raise RuntimeError("Not connected - call connect() first")

        await self._ws.send(
            json.dumps(
                {
                    "type": "input_audio_buffer.commit",
                    "final": True,
                }
            )
        )
        logger.info("Audio stream finalised")

    async def receive_deltas(self) -> AsyncIterator[str]:
        """Yield transcription text deltas until transcription.done is received."""
        if self._ws is None:
            raise RuntimeError("Not connected - call connect() first")

        while True:
            raw = await self._ws.recv()
            msg = json.loads(raw)
            msg_type = msg.get("type")

            if msg_type == "transcription.delta":
                delta = msg.get("delta", "")
                if delta:
                    yield delta

            elif msg_type == "transcription.done":
                logger.info(
                    "Transcription complete, total_text_length=%d",
                    len(msg.get("text", "")),
                )
                return

            elif msg_type == "error":
                error = msg.get("error", "Unknown error")
                logger.error("Voxtral Realtime error: %s", error)
                raise RuntimeError(f"Voxtral Realtime error: {error}")

            else:
                logger.debug("Ignoring message type: %s", msg_type)

    async def disconnect(self) -> None:
        """Close the WebSocket connection."""
        if self._ws is not None:
            await self._ws.close()
            logger.info("Disconnected from Voxtral Realtime")
            self._ws = None


# ---------------------------------------------------------------------------
# File decoding
# ---------------------------------------------------------------------------


def decode_audio_to_pcm(audio_path: str) -> bytes:
    """Decode an audio file (wav/mp3/ogg) to raw PCM16 mono 16kHz bytes.

    Uses the ``wave`` module for WAV files.  For other formats, callers
    should convert to WAV first (e.g. via ffmpeg).
    """
    import wave

    logger.info("Decoding audio to PCM16: %s", audio_path)
    with wave.open(audio_path, "rb") as wf:
        n_channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        framerate = wf.getframerate()
        n_frames = wf.getnframes()
        raw = wf.readframes(n_frames)

    logger.info(
        "WAV: channels=%d, sampwidth=%d, rate=%d, frames=%d",
        n_channels,
        sampwidth,
        framerate,
        n_frames,
    )

    # If stereo, take only the left channel
    if n_channels == 2 and sampwidth == 2:
        import struct

        samples = struct.unpack(f"<{n_frames * 2}h", raw)
        raw = struct.pack(f"<{n_frames}h", *samples[::2])

    return raw


# ---------------------------------------------------------------------------
# File-to-realtime streaming
# ---------------------------------------------------------------------------


async def stream_file_realtime(pcm_data: bytes) -> AsyncIterator[str]:
    """Stream pre-decoded PCM audio through the Voxtral Realtime transcriber.

    Splits *pcm_data* into chunks, sends them to the model, and yields
    text deltas as they arrive.  Audio is sent in a background task so
    that receiving deltas can happen concurrently.
    """
    transcriber = RealtimeTranscriber()
    await transcriber.connect()

    async def _send_audio():
        for offset in range(0, len(pcm_data), CHUNK_SIZE):
            chunk = pcm_data[offset : offset + CHUNK_SIZE]
            await transcriber.send_audio(chunk)
        await transcriber.finish()

    # Launch audio sending concurrently
    import asyncio

    send_task = asyncio.create_task(_send_audio())

    try:
        async for delta in transcriber.receive_deltas():
            yield delta
    finally:
        await send_task
        await transcriber.disconnect()


# ---------------------------------------------------------------------------
# Health check & fallback
# ---------------------------------------------------------------------------


async def is_realtime_available() -> bool:
    """Check whether the vLLM realtime endpoint is reachable."""
    import os

    url = os.getenv("SCW_VOXTRAL_REALTIME_ENDPOINT", "")
    if not url:
        return False

    try:
        import asyncio

        ws_url = get_realtime_ws_url()
        ws = await asyncio.wait_for(websockets.connect(ws_url), timeout=3.0)
        await ws.close()
        return True
    except Exception:
        logger.warning("Voxtral Realtime endpoint not reachable")
        return False


async def transcribe_with_fallback(audio_path: str) -> AsyncIterator[str]:
    """Transcribe audio, preferring realtime streaming with batch fallback.

    If the vLLM realtime endpoint is reachable, decodes the file to PCM
    and streams through the realtime pipeline yielding text deltas.

    If unavailable, falls back to the existing batch diarized transcription
    (``voxtral-small-24b-2507`` on Generative APIs) and yields the complete
    result as a single string.
    """
    if await is_realtime_available():
        logger.info("Using realtime transcription for %s", audio_path)
        pcm = decode_audio_to_pcm(audio_path)
        async for delta in stream_file_realtime(pcm):
            yield delta
    else:
        logger.info("Falling back to batch transcription for %s", audio_path)
        text = transcribe_audio_diarized(audio_path)
        yield text


# ---------------------------------------------------------------------------
# Post-transcription diarization
# ---------------------------------------------------------------------------

_DIARIZATION_PROMPT = (
    "You are given a raw transcript of a doctor-patient conversation. "
    "Label each speaker's turns with 'Doctor:' or 'Patient:' at the start "
    "of each new speaker turn. Output only the diarized transcript, nothing else."
)


def diarize_transcript(raw_text: str) -> str:
    """Send raw transcript to Mistral Small 3.2 for Doctor/Patient labeling."""
    logger.info("Diarizing transcript, length=%d chars", len(raw_text))
    client = get_generative_client()

    response = client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[
            {"role": "system", "content": _DIARIZATION_PROMPT},
            {"role": "user", "content": raw_text},
        ],
    )

    result = response.choices[0].message.content
    logger.info("Diarization complete, length=%d chars", len(result))
    return result
