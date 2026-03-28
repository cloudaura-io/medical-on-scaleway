"""Tests for file-to-realtime streaming — decode audio file and stream through vLLM."""

from __future__ import annotations

import asyncio
import json
import struct
from unittest.mock import AsyncMock, patch, MagicMock

import pytest


def _run(coro):
    return asyncio.run(coro)


def _make_wav_bytes(n_samples: int = 16000, sample_rate: int = 16000) -> bytes:
    """Create a minimal valid WAV file with silent PCM16 audio."""
    n_channels = 1
    bits_per_sample = 16
    byte_rate = sample_rate * n_channels * bits_per_sample // 8
    block_align = n_channels * bits_per_sample // 8
    data_size = n_samples * block_align

    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + data_size,
        b"WAVE",
        b"fmt ",
        16,
        1,  # PCM
        n_channels,
        sample_rate,
        byte_rate,
        block_align,
        bits_per_sample,
        b"data",
        data_size,
    )
    return header + (b"\x00\x00" * n_samples)


class TestDecodeAudioToPcm:
    """Test the audio file decoding utility."""

    def test_decodes_wav_to_pcm16_bytes(self) -> None:
        """decode_audio_to_pcm() must return raw PCM16 bytes from a WAV file."""
        from src.transcription_realtime import decode_audio_to_pcm
        import tempfile, os

        wav = _make_wav_bytes(8000)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(wav)
            path = f.name

        try:
            pcm = decode_audio_to_pcm(path)
            assert isinstance(pcm, bytes)
            assert len(pcm) > 0
            # PCM16 mono 16kHz: each sample is 2 bytes
            assert len(pcm) % 2 == 0
        finally:
            os.unlink(path)


class TestStreamFileRealtime:
    """Test streaming a decoded file through the RealtimeTranscriber."""

    def test_yields_text_deltas_from_file(self) -> None:
        """stream_file_realtime() must yield text deltas from the transcriber."""
        from src.transcription_realtime import stream_file_realtime

        mock_transcriber = AsyncMock()
        mock_transcriber.connect = AsyncMock()
        mock_transcriber.send_audio = AsyncMock()
        mock_transcriber.finish = AsyncMock()
        mock_transcriber.disconnect = AsyncMock()

        async def mock_deltas():
            yield "Hello "
            yield "doctor"

        mock_transcriber.receive_deltas = mock_deltas

        pcm_data = b"\x00\x01" * 2048  # 4096 bytes = 1 chunk

        async def run():
            with patch("src.transcription_realtime.RealtimeTranscriber", return_value=mock_transcriber):
                deltas = []
                async for text in stream_file_realtime(pcm_data):
                    deltas.append(text)
                assert deltas == ["Hello ", "doctor"]

        _run(run())

    def test_sends_audio_in_chunks(self) -> None:
        """stream_file_realtime() must split audio into chunks and send each."""
        from src.transcription_realtime import stream_file_realtime, CHUNK_SIZE

        mock_transcriber = AsyncMock()
        mock_transcriber.connect = AsyncMock()
        mock_transcriber.send_audio = AsyncMock()
        mock_transcriber.finish = AsyncMock()
        mock_transcriber.disconnect = AsyncMock()

        async def mock_deltas():
            yield "text"

        mock_transcriber.receive_deltas = mock_deltas

        # 3 chunks worth of data
        pcm_data = b"\x00" * (CHUNK_SIZE * 3)

        async def run():
            with patch("src.transcription_realtime.RealtimeTranscriber", return_value=mock_transcriber):
                async for _ in stream_file_realtime(pcm_data):
                    pass
                assert mock_transcriber.send_audio.call_count == 3

        _run(run())

    def test_calls_finish_after_all_audio_sent(self) -> None:
        """stream_file_realtime() must call finish() after sending all audio."""
        from src.transcription_realtime import stream_file_realtime

        call_order = []

        mock_transcriber = AsyncMock()
        mock_transcriber.connect = AsyncMock()

        async def track_send(chunk):
            call_order.append("send")

        async def track_finish():
            call_order.append("finish")

        mock_transcriber.send_audio = track_send
        mock_transcriber.finish = track_finish
        mock_transcriber.disconnect = AsyncMock()

        async def mock_deltas():
            yield "done"

        mock_transcriber.receive_deltas = mock_deltas

        pcm_data = b"\x00" * 4096

        async def run():
            with patch("src.transcription_realtime.RealtimeTranscriber", return_value=mock_transcriber):
                async for _ in stream_file_realtime(pcm_data):
                    pass
                assert "finish" in call_order
                assert call_order.index("finish") > call_order.index("send")

        _run(run())
