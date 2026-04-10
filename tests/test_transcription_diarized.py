"""Tests for transcribe_audio_diarized() in src/transcription.py."""

from __future__ import annotations

import base64
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure project root is on sys.path so `src.*` imports work
_project_root = str(Path(__file__).resolve().parents[1])
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


# ---------------------------------------------------------------------------
# Tests: transcribe_audio_diarized()
# ---------------------------------------------------------------------------


class TestTranscribeAudioDiarizedCallsChat:
    """transcribe_audio_diarized() must call chat completions with audio_url."""

    def test_calls_chat_completions_with_audio_url(self) -> None:
        """The function must call client.chat.completions.create() with an
        audio_url content part containing base64-encoded audio data."""
        env = {
            "SCW_GENERATIVE_API_URL": "https://fake.api",
            "SCW_SECRET_KEY": "fake-key",
        }

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Doctor: Hello\nPatient: Hi"

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        with patch.dict(os.environ, env, clear=False):
            from src.config import get_generative_client

            get_generative_client.cache_clear()

            with patch("src.transcription.get_generative_client", return_value=mock_client):
                from src.transcription import transcribe_audio_diarized

                # Create a temporary audio file
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                    tmp.write(b"fake audio bytes")
                    tmp_path = tmp.name

                try:
                    transcribe_audio_diarized(tmp_path)
                finally:
                    Path(tmp_path).unlink(missing_ok=True)

        # Verify chat.completions.create was called
        mock_client.chat.completions.create.assert_called_once()
        call_kwargs = mock_client.chat.completions.create.call_args

        # Check the messages contain audio_url content part
        messages = call_kwargs.kwargs.get("messages") or call_kwargs[1].get("messages")
        assert messages is not None
        assert len(messages) >= 1

        # Find the user message
        user_msgs = [m for m in messages if m["role"] == "user"]
        assert len(user_msgs) == 1

        user_content = user_msgs[0]["content"]
        assert isinstance(user_content, list), "User content must be a list of content parts"

        # Find the audio_url part
        audio_parts = [p for p in user_content if p.get("type") == "input_audio"]
        assert len(audio_parts) == 1, "Must include exactly one input_audio content part"

        audio_url = audio_parts[0]["input_audio"]["data"]
        # Verify it's base64-encoded
        expected_b64 = base64.b64encode(b"fake audio bytes").decode()
        assert audio_url == expected_b64


class TestTranscribeAudioDiarizedPrompt:
    """The diarization prompt must include speaker labeling instructions."""

    def test_prompt_includes_speaker_labels(self) -> None:
        """The user message text must instruct the model to label speakers
        as Doctor and Patient."""
        env = {
            "SCW_GENERATIVE_API_URL": "https://fake.api",
            "SCW_SECRET_KEY": "fake-key",
        }

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Doctor: Hello\nPatient: Hi"

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        with patch.dict(os.environ, env, clear=False):
            from src.config import get_generative_client

            get_generative_client.cache_clear()

            with patch("src.transcription.get_generative_client", return_value=mock_client):
                from src.transcription import transcribe_audio_diarized

                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                    tmp.write(b"fake audio bytes")
                    tmp_path = tmp.name

                try:
                    transcribe_audio_diarized(tmp_path)
                finally:
                    Path(tmp_path).unlink(missing_ok=True)

        call_kwargs = mock_client.chat.completions.create.call_args
        messages = call_kwargs.kwargs.get("messages") or call_kwargs[1].get("messages")
        user_msg = [m for m in messages if m["role"] == "user"][0]

        # Find text content parts
        text_parts = [p for p in user_msg["content"] if p.get("type") == "text"]
        assert len(text_parts) >= 1, "Must include at least one text content part"

        prompt_text = text_parts[0]["text"].lower()
        assert "doctor" in prompt_text, "Prompt must mention 'Doctor' speaker label"
        assert "patient" in prompt_text, "Prompt must mention 'Patient' speaker label"


class TestTranscribeAudioDiarizedNoSystemMessage:
    """No system message must be used - only user message."""

    def test_no_system_message(self) -> None:
        """The messages list must not contain any system messages."""
        env = {
            "SCW_GENERATIVE_API_URL": "https://fake.api",
            "SCW_SECRET_KEY": "fake-key",
        }

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Doctor: Hello"

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        with patch.dict(os.environ, env, clear=False):
            from src.config import get_generative_client

            get_generative_client.cache_clear()

            with patch("src.transcription.get_generative_client", return_value=mock_client):
                from src.transcription import transcribe_audio_diarized

                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                    tmp.write(b"fake audio bytes")
                    tmp_path = tmp.name

                try:
                    transcribe_audio_diarized(tmp_path)
                finally:
                    Path(tmp_path).unlink(missing_ok=True)

        call_kwargs = mock_client.chat.completions.create.call_args
        messages = call_kwargs.kwargs.get("messages") or call_kwargs[1].get("messages")

        system_msgs = [m for m in messages if m["role"] == "system"]
        assert len(system_msgs) == 0, "No system message should be used with audio input"


class TestTranscribeAudioDiarizedReturnsText:
    """The function must return the model's text response."""

    def test_returns_model_response_text(self) -> None:
        """transcribe_audio_diarized() must return the text from the model response."""
        env = {
            "SCW_GENERATIVE_API_URL": "https://fake.api",
            "SCW_SECRET_KEY": "fake-key",
        }

        expected_text = "Doctor: How are you feeling today?\nPatient: I have a headache."

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = expected_text

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        with patch.dict(os.environ, env, clear=False):
            from src.config import get_generative_client

            get_generative_client.cache_clear()

            with patch("src.transcription.get_generative_client", return_value=mock_client):
                from src.transcription import transcribe_audio_diarized

                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                    tmp.write(b"fake audio bytes")
                    tmp_path = tmp.name

                try:
                    result = transcribe_audio_diarized(tmp_path)
                finally:
                    Path(tmp_path).unlink(missing_ok=True)

        assert result == expected_text
