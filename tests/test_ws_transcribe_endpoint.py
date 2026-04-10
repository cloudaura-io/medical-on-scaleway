"""Tests for WebSocket /ws/transcribe endpoint and post-transcription diarization."""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

_project_root = str(Path(__file__).resolve().parents[1])
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

_app_dir = str(Path(__file__).resolve().parents[1] / "01_consultation_assistant")
if _app_dir not in sys.path:
    sys.path.insert(0, _app_dir)


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def client():
    """Return a TestClient for the doctor assistant app."""
    env_patch = patch.dict(
        os.environ,
        {
            "SCW_GENERATIVE_API_URL": "https://fake.api",
            "SCW_SECRET_KEY": "fake-key",
            "SCW_VOXTRAL_REALTIME_ENDPOINT": "http://fake:8000/v1",
        },
    )
    env_patch.start()

    from src.config import get_generative_client

    get_generative_client.cache_clear()

    if "main" in sys.modules:
        del sys.modules["main"]

    importlib.invalidate_caches()
    import main as ambient_main

    yield TestClient(ambient_main.app)

    env_patch.stop()


# ---------------------------------------------------------------------------
# Tests: WebSocket /ws/transcribe
# ---------------------------------------------------------------------------


class TestWsTranscribeEndpoint:
    """Test the WebSocket /ws/transcribe route exists and handles messages."""

    def test_websocket_route_exists(self, client: TestClient) -> None:
        """The /ws/transcribe WebSocket route must be registered."""
        import main as ambient_main

        routes = [r.path for r in ambient_main.app.routes]
        assert "/ws/transcribe" in routes

    def test_websocket_sends_delta_messages(self, client: TestClient) -> None:
        """The endpoint must forward transcription deltas as JSON messages."""

        async def mock_deltas():
            yield "Hello "
            yield "world"

        mock_transcriber = AsyncMock()
        mock_transcriber.connect = AsyncMock()
        mock_transcriber.send_audio = AsyncMock()
        mock_transcriber.finish = AsyncMock()
        mock_transcriber.disconnect = AsyncMock()
        mock_transcriber.receive_deltas = mock_deltas

        with (
            patch("main.RealtimeTranscriber", return_value=mock_transcriber),
            client.websocket_connect("/ws/transcribe") as ws,
        ):
            # Send some audio
            ws.send_bytes(b"\x00\x01" * 2048)
            # Send stop signal
            ws.send_json({"type": "stop"})
            # Collect responses
            messages = []
            while True:
                try:
                    msg = ws.receive_json(mode="text")
                    messages.append(msg)
                    if msg.get("type") in ("done", "error"):
                        break
                except Exception:
                    break

        delta_msgs = [m for m in messages if m.get("type") == "delta"]
        assert len(delta_msgs) >= 1

    def test_websocket_sends_done_message(self, client: TestClient) -> None:
        """After transcription completes, the endpoint must send a done message."""

        async def mock_deltas():
            yield "text"

        mock_transcriber = AsyncMock()
        mock_transcriber.connect = AsyncMock()
        mock_transcriber.send_audio = AsyncMock()
        mock_transcriber.finish = AsyncMock()
        mock_transcriber.disconnect = AsyncMock()
        mock_transcriber.receive_deltas = mock_deltas

        with (
            patch("main.RealtimeTranscriber", return_value=mock_transcriber),
            patch("main.diarize_transcript", return_value="Doctor: text"),
            client.websocket_connect("/ws/transcribe") as ws,
        ):
            ws.send_json({"type": "stop"})
            messages = []
            while True:
                try:
                    msg = ws.receive_json(mode="text")
                    messages.append(msg)
                    if msg.get("type") in ("done", "error"):
                        break
                except Exception:
                    break

        types = [m.get("type") for m in messages]
        assert "done" in types


# ---------------------------------------------------------------------------
# Tests: Post-transcription diarization
# ---------------------------------------------------------------------------


class TestPostTranscriptionDiarization:
    """Test that raw transcript is sent to Mistral Small for diarization."""

    def test_diarize_raw_transcript(self) -> None:
        """diarize_transcript() must call Mistral Small and return labeled text."""
        from src.transcription_realtime import diarize_transcript

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Doctor: Hello\nPatient: Hi"))]

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        with patch("src.transcription_realtime.get_generative_client", return_value=mock_client):
            result = diarize_transcript("Hello how are you I have a headache")

        assert "Doctor:" in result
        assert "Patient:" in result
        mock_client.chat.completions.create.assert_called_once()

    def test_diarize_uses_chat_model(self) -> None:
        """diarize_transcript() must use the CHAT_MODEL for diarization."""
        from src.config import CHAT_MODEL
        from src.transcription_realtime import diarize_transcript

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Doctor: Hi\nPatient: Hello"))]

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        with patch("src.transcription_realtime.get_generative_client", return_value=mock_client):
            diarize_transcript("some transcript")

        call_kwargs = mock_client.chat.completions.create.call_args
        assert call_kwargs.kwargs.get("model") == CHAT_MODEL or call_kwargs[1].get("model") == CHAT_MODEL
