"""Tests for the POST /api/transcribe-stream SSE endpoint in 01_ambient_scribe."""

from __future__ import annotations

import importlib
import json
import os
import sys
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

# Ensure project root is on sys.path so `src.*` imports work
_project_root = str(Path(__file__).resolve().parents[1])
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# Ensure the ambient scribe directory is on sys.path
_app_dir = str(Path(__file__).resolve().parents[1] / "01_ambient_scribe")
if _app_dir not in sys.path:
    sys.path.insert(0, _app_dir)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_sse_events(response_text: str) -> list[dict]:
    """Parse an SSE text stream into a list of JSON payloads."""
    events = []
    for line in response_text.strip().split("\n"):
        line = line.strip()
        if line.startswith("data: "):
            payload_str = line[len("data: "):]
            try:
                events.append(json.loads(payload_str))
            except json.JSONDecodeError:
                continue
    return events


# ---------------------------------------------------------------------------
# Fixture: ambient scribe app
# ---------------------------------------------------------------------------

@pytest.fixture()
def client():
    """Return a TestClient for the ambient scribe app.

    The app module is imported inside a patched environment so that
    ``validate_config`` does not raise on CI where env vars may be
    absent.
    """
    env_patch = patch.dict(
        os.environ,
        {
            "SCW_GENERATIVE_API_URL": "https://fake.api",
            "SCW_SECRET_KEY": "fake-key",
        },
    )
    env_patch.start()

    # Clear the lru_cache to avoid stale clients from prior tests
    from src.config import get_generative_client
    get_generative_client.cache_clear()

    # Remove cached module so reimport picks up the patched env
    if "main" in sys.modules:
        del sys.modules["main"]

    importlib.invalidate_caches()
    import main as ambient_main

    yield TestClient(ambient_main.app)

    env_patch.stop()


# ---------------------------------------------------------------------------
# Tests: POST /api/transcribe-stream
# ---------------------------------------------------------------------------


class TestTranscribeStreamContentType:
    """POST /api/transcribe-stream must return text/event-stream."""

    def test_returns_event_stream_content_type(self, client: TestClient) -> None:
        """The response Content-Type must be text/event-stream."""
        fake_chunks = ["Hello ", "world ", "this is a test."]

        def mock_stream(audio_path: str):
            yield from fake_chunks

        with patch("main.transcribe_audio_stream", mock_stream):
            audio = BytesIO(b"fake audio content")
            response = client.post(
                "/api/transcribe-stream",
                files={"file": ("test.wav", audio, "audio/wav")},
            )

        assert response.status_code == 200
        content_type = response.headers.get("content-type", "")
        assert "text/event-stream" in content_type


class TestTranscribeStreamEventFormat:
    """SSE events must contain transcript_chunk with text field."""

    def test_emits_transcript_chunk_events(self, client: TestClient) -> None:
        """Each chunk must produce an SSE event with event=transcript_chunk."""
        fake_chunks = ["Hello ", "world."]

        def mock_stream(audio_path: str):
            yield from fake_chunks

        with patch("main.transcribe_audio_stream", mock_stream):
            audio = BytesIO(b"fake audio content")
            response = client.post(
                "/api/transcribe-stream",
                files={"file": ("test.wav", audio, "audio/wav")},
            )

        events = _parse_sse_events(response.text)
        chunk_events = [e for e in events if e.get("event") == "transcript_chunk"]

        assert len(chunk_events) == 2
        assert chunk_events[0]["text"] == "Hello "
        assert chunk_events[1]["text"] == "world."


class TestTranscribeStreamDoneEvent:
    """A final transcript_done event must be emitted."""

    def test_emits_transcript_done_event(self, client: TestClient) -> None:
        """The stream must end with a transcript_done event."""
        fake_chunks = ["Test chunk."]

        def mock_stream(audio_path: str):
            yield from fake_chunks

        with patch("main.transcribe_audio_stream", mock_stream):
            audio = BytesIO(b"fake audio content")
            response = client.post(
                "/api/transcribe-stream",
                files={"file": ("test.wav", audio, "audio/wav")},
            )

        events = _parse_sse_events(response.text)
        done_events = [e for e in events if e.get("event") == "transcript_done"]

        assert len(done_events) == 1


class TestTranscribeStreamErrorHandling:
    """Error cases must yield SSE error events."""

    def test_missing_file_returns_422(self, client: TestClient) -> None:
        """POST without a file must return an HTTP 422."""
        response = client.post("/api/transcribe-stream")
        assert response.status_code == 422

    def test_api_failure_yields_error_event(self, client: TestClient) -> None:
        """When the stream generator raises, an SSE error event must be emitted."""

        def mock_stream_fails(audio_path: str):
            raise RuntimeError("API connection failed")
            yield  # pragma: no cover — makes this a generator

        with patch("main.transcribe_audio_stream", mock_stream_fails):
            audio = BytesIO(b"fake audio content")
            response = client.post(
                "/api/transcribe-stream",
                files={"file": ("test.wav", audio, "audio/wav")},
            )

        # The response should still be 200 (SSE stream) but contain an error event
        assert response.status_code == 200
        events = _parse_sse_events(response.text)
        error_events = [e for e in events if e.get("event") == "error"]
        assert len(error_events) >= 1
        assert "API connection failed" in error_events[0]["detail"]
