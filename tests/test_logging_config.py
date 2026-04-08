"""Tests for src/logging_config.py — logging setup and timed_operation decorator."""

from __future__ import annotations

import asyncio
import logging

import pytest

# ---------------------------------------------------------------------------
# Tests: configure_logging()
# ---------------------------------------------------------------------------


class TestConfigureLogging:
    """Test the configure_logging() function."""

    def test_sets_correct_log_level(self) -> None:
        """configure_logging() must set the root logger to the given level."""
        from src.logging_config import configure_logging

        configure_logging(level=logging.WARNING)
        root = logging.getLogger()
        assert root.level == logging.WARNING

        # Reset
        configure_logging(level=logging.INFO)

    def test_default_level_is_info(self) -> None:
        """configure_logging() must default to INFO level."""
        from src.logging_config import configure_logging

        configure_logging()
        root = logging.getLogger()
        assert root.level == logging.INFO

    def test_sets_consistent_format(self) -> None:
        """configure_logging() must configure a handler with timestamp and module name."""
        from src.logging_config import configure_logging

        configure_logging()
        root = logging.getLogger()

        # At least one handler should be present
        assert len(root.handlers) > 0

        # Find a handler whose format contains both asctime and name
        found = False
        for handler in root.handlers:
            fmt = handler.formatter._fmt if handler.formatter else ""
            if "%(asctime)s" in fmt and "%(name)s" in fmt:
                found = True
                break
        assert found, "No handler found with %(asctime)s and %(name)s in format"

    def test_adds_handler(self) -> None:
        """configure_logging() must add a StreamHandler to the root logger."""
        from src.logging_config import configure_logging

        configure_logging()
        root = logging.getLogger()
        handler_types = [type(h).__name__ for h in root.handlers]
        assert "StreamHandler" in handler_types

    def test_does_not_add_duplicate_handlers(self) -> None:
        """Calling configure_logging() twice must not duplicate handlers."""
        from src.logging_config import configure_logging

        configure_logging()
        count1 = len(logging.getLogger().handlers)
        configure_logging()
        count2 = len(logging.getLogger().handlers)
        assert count2 == count1


# ---------------------------------------------------------------------------
# Tests: timed_operation decorator (sync)
# ---------------------------------------------------------------------------


class TestTimedOperationSync:
    """Test the timed_operation decorator with synchronous functions."""

    def test_sync_function_returns_correct_result(self) -> None:
        """timed_operation must not alter the return value of sync functions."""
        from src.logging_config import timed_operation

        @timed_operation
        def add(a: int, b: int) -> int:
            return a + b

        assert add(2, 3) == 5

    def test_sync_function_logs_elapsed_time(self, caplog: pytest.LogCaptureFixture) -> None:
        """timed_operation must log the elapsed time for sync functions."""
        from src.logging_config import timed_operation

        @timed_operation
        def slow_add(a: int, b: int) -> int:
            return a + b

        with caplog.at_level(logging.DEBUG):
            slow_add(1, 2)

        # Check that a log record mentions elapsed time
        matching = [r for r in caplog.records if "slow_add" in r.message and "s" in r.message]
        assert len(matching) > 0

    def test_sync_function_preserves_exceptions(self) -> None:
        """timed_operation must re-raise exceptions from sync functions."""
        from src.logging_config import timed_operation

        @timed_operation
        def failing() -> None:
            raise ValueError("boom")

        with pytest.raises(ValueError, match="boom"):
            failing()


# ---------------------------------------------------------------------------
# Tests: timed_operation decorator (async)
# ---------------------------------------------------------------------------


class TestTimedOperationAsync:
    """Test the timed_operation decorator with async functions."""

    def test_async_function_returns_correct_result(self) -> None:
        """timed_operation must not alter the return value of async functions."""
        from src.logging_config import timed_operation

        @timed_operation
        async def async_add(a: int, b: int) -> int:
            return a + b

        result = asyncio.run(async_add(2, 3))
        assert result == 5

    def test_async_function_logs_elapsed_time(self, caplog: pytest.LogCaptureFixture) -> None:
        """timed_operation must log the elapsed time for async functions."""
        from src.logging_config import timed_operation

        @timed_operation
        async def async_work() -> str:
            return "done"

        with caplog.at_level(logging.DEBUG):
            asyncio.run(async_work())

        matching = [r for r in caplog.records if "async_work" in r.message and "s" in r.message]
        assert len(matching) > 0

    def test_async_function_preserves_exceptions(self) -> None:
        """timed_operation must re-raise exceptions from async functions."""
        from src.logging_config import timed_operation

        @timed_operation
        async def async_failing() -> None:
            raise RuntimeError("async boom")

        with pytest.raises(RuntimeError, match="async boom"):
            asyncio.run(async_failing())
