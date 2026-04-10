"""Tests for src/transcription_realtime.py - Voxtral Realtime streaming."""

from __future__ import annotations

import asyncio
import base64
import json
from unittest.mock import AsyncMock, patch

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run(coro):
    """Run an async coroutine in a new event loop (Python 3.14 compat)."""
    return asyncio.run(coro)


def _make_pcm_chunk(n_bytes: int = 4096) -> bytes:
    """Return dummy PCM16 audio bytes."""
    return b"\x00\x01" * (n_bytes // 2)


def _mock_connect(mock_ws):
    """Create a mock for websockets.connect that works as both awaitable and async ctx manager."""

    async def connect(*args, **kwargs):
        return mock_ws

    return connect


# ---------------------------------------------------------------------------
# Tests: get_realtime_ws_url
# ---------------------------------------------------------------------------


class TestGetRealtimeWsUrl:
    """Test the WebSocket URL builder in config."""

    def test_converts_http_to_ws(self) -> None:
        from src.config import get_realtime_ws_url

        with patch.dict("os.environ", {"SCW_VOXTRAL_REALTIME_ENDPOINT": "http://1.2.3.4:8000/v1"}):
            url = get_realtime_ws_url()
        assert url == "ws://1.2.3.4:8000/v1/realtime"

    def test_converts_https_to_wss(self) -> None:
        from src.config import get_realtime_ws_url

        with patch.dict("os.environ", {"SCW_VOXTRAL_REALTIME_ENDPOINT": "https://host.com/v1"}):
            url = get_realtime_ws_url()
        assert url == "wss://host.com/v1/realtime"

    def test_strips_trailing_slash(self) -> None:
        from src.config import get_realtime_ws_url

        with patch.dict("os.environ", {"SCW_VOXTRAL_REALTIME_ENDPOINT": "http://host:8000/v1/"}):
            url = get_realtime_ws_url()
        assert url == "ws://host:8000/v1/realtime"


# ---------------------------------------------------------------------------
# Tests: RealtimeTranscriber
# ---------------------------------------------------------------------------


class TestRealtimeTranscriber:
    """Test the async realtime transcription class."""

    def test_connect_sends_session_update(self) -> None:
        """On connect, the transcriber must send session.update with the model."""
        from src.transcription_realtime import RealtimeTranscriber

        mock_ws = AsyncMock()
        mock_ws.recv = AsyncMock(
            return_value=json.dumps(
                {
                    "type": "session.created",
                    "id": "sess-123",
                }
            )
        )

        async def run():
            with (
                patch("src.transcription_realtime.websockets.connect", _mock_connect(mock_ws)),
                patch("src.transcription_realtime.get_realtime_ws_url", return_value="ws://fake:8000/v1/realtime"),
            ):
                t = RealtimeTranscriber()
                await t.connect()
                calls = [json.loads(c.args[0]) for c in mock_ws.send.call_args_list]
                types = [c["type"] for c in calls]
                assert "session.update" in types

        _run(run())

    def test_send_audio_encodes_base64(self) -> None:
        """send_audio() must base64-encode the PCM chunk."""
        from src.transcription_realtime import RealtimeTranscriber

        mock_ws = AsyncMock()
        mock_ws.recv = AsyncMock(
            return_value=json.dumps(
                {
                    "type": "session.created",
                    "id": "s1",
                }
            )
        )
        chunk = _make_pcm_chunk(256)

        async def run():
            with (
                patch("src.transcription_realtime.websockets.connect", _mock_connect(mock_ws)),
                patch("src.transcription_realtime.get_realtime_ws_url", return_value="ws://fake:8000/v1/realtime"),
            ):
                t = RealtimeTranscriber()
                await t.connect()
                mock_ws.send.reset_mock()
                await t.send_audio(chunk)
                msg = json.loads(mock_ws.send.call_args.args[0])
                assert msg["type"] == "input_audio_buffer.append"
                decoded = base64.b64decode(msg["audio"])
                assert decoded == chunk

        _run(run())

    def test_finish_sends_final_commit(self) -> None:
        """finish() must send input_audio_buffer.commit with final=True."""
        from src.transcription_realtime import RealtimeTranscriber

        mock_ws = AsyncMock()
        mock_ws.recv = AsyncMock(
            return_value=json.dumps(
                {
                    "type": "session.created",
                    "id": "s1",
                }
            )
        )

        async def run():
            with (
                patch("src.transcription_realtime.websockets.connect", _mock_connect(mock_ws)),
                patch("src.transcription_realtime.get_realtime_ws_url", return_value="ws://fake:8000/v1/realtime"),
            ):
                t = RealtimeTranscriber()
                await t.connect()
                mock_ws.send.reset_mock()
                await t.finish()
                msg = json.loads(mock_ws.send.call_args.args[0])
                assert msg["type"] == "input_audio_buffer.commit"
                assert msg.get("final") is True

        _run(run())

    def test_receive_yields_delta_text(self) -> None:
        """receive_deltas() must yield text from transcription.delta events."""
        from src.transcription_realtime import RealtimeTranscriber

        responses = [
            json.dumps({"type": "session.created", "id": "s1"}),
            json.dumps({"type": "transcription.delta", "delta": "Hello "}),
            json.dumps({"type": "transcription.delta", "delta": "world"}),
            json.dumps({"type": "transcription.done", "text": "Hello world"}),
        ]
        recv_index = 0

        async def mock_recv():
            nonlocal recv_index
            resp = responses[recv_index]
            recv_index += 1
            return resp

        mock_ws = AsyncMock()
        mock_ws.recv = mock_recv

        async def run():
            with (
                patch("src.transcription_realtime.websockets.connect", _mock_connect(mock_ws)),
                patch("src.transcription_realtime.get_realtime_ws_url", return_value="ws://fake:8000/v1/realtime"),
            ):
                t = RealtimeTranscriber()
                await t.connect()
                deltas = []
                async for text in t.receive_deltas():
                    deltas.append(text)
                assert deltas == ["Hello ", "world"]

        _run(run())

    def test_disconnect_closes_websocket(self) -> None:
        """disconnect() must close the WebSocket connection."""
        from src.transcription_realtime import RealtimeTranscriber

        mock_ws = AsyncMock()
        mock_ws.recv = AsyncMock(
            return_value=json.dumps(
                {
                    "type": "session.created",
                    "id": "s1",
                }
            )
        )

        async def run():
            with (
                patch("src.transcription_realtime.websockets.connect", _mock_connect(mock_ws)),
                patch("src.transcription_realtime.get_realtime_ws_url", return_value="ws://fake:8000/v1/realtime"),
            ):
                t = RealtimeTranscriber()
                await t.connect()
                await t.disconnect()
                mock_ws.close.assert_called_once()

        _run(run())
