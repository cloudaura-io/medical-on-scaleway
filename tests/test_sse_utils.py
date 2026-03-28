"""Tests for src/sse_utils.py — SSE formatting and streaming utilities."""

from __future__ import annotations

import asyncio
import json

import pytest


# ---------------------------------------------------------------------------
# Tests: format_sse_event()
# ---------------------------------------------------------------------------

class TestFormatSseEvent:
    """Test the format_sse_event() function."""

    def test_produces_correct_sse_format(self) -> None:
        """format_sse_event() must produce 'data: {json}\n\n' output."""
        from src.sse_utils import format_sse_event

        result = format_sse_event("progress", {"page": 1, "total": 5})
        assert result.startswith("data: ")
        assert result.endswith("\n\n")

        # Parse the JSON payload between 'data: ' and '\n\n'
        payload_str = result[len("data: "):-2]
        payload = json.loads(payload_str)
        assert payload["event"] == "progress"
        assert payload["page"] == 1
        assert payload["total"] == 5

    def test_handles_progress_event(self) -> None:
        """format_sse_event() must correctly format a progress event."""
        from src.sse_utils import format_sse_event

        result = format_sse_event("progress", {"step": 3, "total": 10})
        payload = json.loads(result[len("data: "):-2])
        assert payload["event"] == "progress"
        assert payload["step"] == 3
        assert payload["total"] == 10

    def test_handles_error_event(self) -> None:
        """format_sse_event() must correctly format an error event."""
        from src.sse_utils import format_sse_event

        result = format_sse_event("error", {"detail": "Something went wrong"})
        payload = json.loads(result[len("data: "):-2])
        assert payload["event"] == "error"
        assert payload["detail"] == "Something went wrong"

    def test_handles_complete_event(self) -> None:
        """format_sse_event() must correctly format a complete event."""
        from src.sse_utils import format_sse_event

        result = format_sse_event(
            "complete",
            {"filename": "report.pdf", "pages": 5, "chunks": 12},
        )
        payload = json.loads(result[len("data: "):-2])
        assert payload["event"] == "complete"
        assert payload["filename"] == "report.pdf"
        assert payload["pages"] == 5
        assert payload["chunks"] == 12

    def test_handles_empty_data(self) -> None:
        """format_sse_event() must work when data dict is empty."""
        from src.sse_utils import format_sse_event

        result = format_sse_event("ping", {})
        payload = json.loads(result[len("data: "):-2])
        assert payload["event"] == "ping"

    def test_returns_string(self) -> None:
        """format_sse_event() must return a string."""
        from src.sse_utils import format_sse_event

        result = format_sse_event("test", {"key": "value"})
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# Tests: safe_streaming_wrapper()
# ---------------------------------------------------------------------------

class TestSafeStreamingWrapper:
    """Test the safe_streaming_wrapper() async generator wrapper."""

    def test_yields_events_from_successful_generator(self) -> None:
        """safe_streaming_wrapper() must pass through events from a healthy generator."""
        from src.sse_utils import safe_streaming_wrapper

        async def good_generator():
            yield "data: {\"event\": \"step1\"}\n\n"
            yield "data: {\"event\": \"step2\"}\n\n"

        async def collect():
            results = []
            async for event in safe_streaming_wrapper(good_generator()):
                results.append(event)
            return results

        results = asyncio.get_event_loop().run_until_complete(collect())
        assert len(results) == 2
        assert "step1" in results[0]
        assert "step2" in results[1]

    def test_catches_exception_and_yields_error_event(self) -> None:
        """safe_streaming_wrapper() must catch exceptions and yield a standardised error SSE event."""
        from src.sse_utils import safe_streaming_wrapper

        async def failing_generator():
            yield "data: {\"event\": \"step1\"}\n\n"
            raise RuntimeError("OCR processing failed")

        async def collect():
            results = []
            async for event in safe_streaming_wrapper(failing_generator()):
                results.append(event)
            return results

        results = asyncio.get_event_loop().run_until_complete(collect())

        # Should have the first event + the error event
        assert len(results) == 2

        # First event passes through
        assert "step1" in results[0]

        # Second event is the error
        error_payload = json.loads(results[1][len("data: "):-2])
        assert error_payload["event"] == "error"
        assert "OCR processing failed" in error_payload["detail"]

    def test_handles_generator_with_no_events_before_error(self) -> None:
        """safe_streaming_wrapper() must handle immediate failure."""
        from src.sse_utils import safe_streaming_wrapper

        async def immediate_fail():
            raise ValueError("Bad input")
            yield  # pragma: no cover — makes this an async generator

        async def collect():
            results = []
            async for event in safe_streaming_wrapper(immediate_fail()):
                results.append(event)
            return results

        results = asyncio.get_event_loop().run_until_complete(collect())

        assert len(results) == 1
        error_payload = json.loads(results[0][len("data: "):-2])
        assert error_payload["event"] == "error"
        assert "Bad input" in error_payload["detail"]
