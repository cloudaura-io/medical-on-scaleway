"""
Realtime audio transcription via Voxtral Mini 4B on self-hosted vLLM.

Connects to the vLLM ``/v1/realtime`` WebSocket endpoint, streams PCM16
audio chunks, and yields transcription text deltas as they arrive.

Protocol (vLLM Realtime API):
  1. Client opens WebSocket → server sends ``session.created``
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
from typing import AsyncIterator

import websockets

from src.config import REALTIME_STT_MODEL, get_realtime_ws_url

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
        await self._ws.send(json.dumps({
            "type": "session.update",
            "model": f"mistralai/{REALTIME_STT_MODEL}",
        }))

        # Send initial commit (signals ready to receive audio)
        await self._ws.send(json.dumps({
            "type": "input_audio_buffer.commit",
        }))
        logger.info("Session initialised, ready for audio")

    async def send_audio(self, chunk: bytes) -> None:
        """Send a PCM16 audio chunk (base64-encoded) to the model."""
        if self._ws is None:
            raise RuntimeError("Not connected — call connect() first")

        encoded = base64.b64encode(chunk).decode("utf-8")
        await self._ws.send(json.dumps({
            "type": "input_audio_buffer.append",
            "audio": encoded,
        }))

    async def finish(self) -> None:
        """Signal that all audio has been sent."""
        if self._ws is None:
            raise RuntimeError("Not connected — call connect() first")

        await self._ws.send(json.dumps({
            "type": "input_audio_buffer.commit",
            "final": True,
        }))
        logger.info("Audio stream finalised")

    async def receive_deltas(self) -> AsyncIterator[str]:
        """Yield transcription text deltas until transcription.done is received."""
        if self._ws is None:
            raise RuntimeError("Not connected — call connect() first")

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
        n_channels, sampwidth, framerate, n_frames,
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
