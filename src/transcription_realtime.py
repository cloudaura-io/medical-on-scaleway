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
