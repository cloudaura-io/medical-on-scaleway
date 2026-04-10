"""Tests for the POST /api/transcribe endpoint with diarized transcription."""

from __future__ import annotations

import importlib
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

# Ensure the doctor assistant directory is on sys.path
_app_dir = str(Path(__file__).resolve().parents[1] / "01_consultation_assistant")
if _app_dir not in sys.path:
    sys.path.insert(0, _app_dir)


# ---------------------------------------------------------------------------
# Fixture: doctor assistant app
# ---------------------------------------------------------------------------


@pytest.fixture()
def client():
    """Return a TestClient for the doctor assistant app."""
    env_patch = patch.dict(
        os.environ,
        {
            "SCW_GENERATIVE_API_URL": "https://fake.api",
            "SCW_SECRET_KEY": "fake-key",
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
# Tests: POST /api/transcribe (diarized)
# ---------------------------------------------------------------------------


class TestTranscribeEndpointReturnsJson:
    """POST /api/transcribe must accept file upload and return JSON."""

    def test_accepts_file_upload_returns_transcript(self, client: TestClient) -> None:
        """The endpoint must accept a file upload and return {"transcript": "..."}."""
        diarized_text = "Doctor: Hello, how are you?\nPatient: I have a headache."

        with patch("main.transcribe_audio_diarized", return_value=diarized_text):
            audio = BytesIO(b"fake audio content")
            response = client.post(
                "/api/transcribe",
                files={"file": ("test.wav", audio, "audio/wav")},
            )

        assert response.status_code == 200
        data = response.json()
        assert "transcript" in data
        assert data["transcript"] == diarized_text


class TestTranscribeEndpointSpeakerLabels:
    """The transcript returned must contain speaker labels."""

    def test_transcript_contains_speaker_labels(self, client: TestClient) -> None:
        """The returned transcript must contain Doctor: and Patient: labels."""
        diarized_text = (
            "Doctor: Good morning. What brings you in today?\nPatient: I've been having chest pain for two days."
        )

        with patch("main.transcribe_audio_diarized", return_value=diarized_text):
            audio = BytesIO(b"fake audio content")
            response = client.post(
                "/api/transcribe",
                files={"file": ("test.wav", audio, "audio/wav")},
            )

        assert response.status_code == 200
        transcript = response.json()["transcript"]
        assert "Doctor:" in transcript
        assert "Patient:" in transcript
