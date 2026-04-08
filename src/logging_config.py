"""
Shared logging configuration for all showcase applications.

Provides:
- ``configure_logging()`` — sets a consistent log format and level
  across all modules.
- ``timed_operation`` — a decorator that logs elapsed wall-clock time
  for both sync and async functions, replacing ad-hoc
  ``time.perf_counter()`` patterns.
"""

from __future__ import annotations

import functools
import inspect
import logging
import sys
import time
from collections.abc import Callable
from typing import Any, TypeVar

# Sentinel to track whether configure_logging() has already run.
_CONFIGURED = False

# Standard log format: timestamp, level, module name, message.
_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

F = TypeVar("F", bound=Callable[..., Any])


# ------------------------------------------------------------------
# Logging setup
# ------------------------------------------------------------------


def configure_logging(
    level: int = logging.INFO,
) -> None:
    """Configure the root logger with a consistent format.

    Sets the root logger's level and attaches a ``StreamHandler``
    writing to ``stderr`` with a standard format that includes
    timestamps and module names.

    Safe to call multiple times — subsequent calls update the level
    but do not duplicate handlers.

    Args:
        level: The logging level to set (default ``logging.INFO``).
    """
    global _CONFIGURED

    root = logging.getLogger()
    root.setLevel(level)

    if not _CONFIGURED:
        handler = logging.StreamHandler(sys.stderr)
        handler.setLevel(level)
        formatter = logging.Formatter(
            fmt=_LOG_FORMAT,
            datefmt=_DATE_FORMAT,
        )
        handler.setFormatter(formatter)
        root.addHandler(handler)

        # Force uvicorn loggers to use the same format instead of
        # their own handlers (which bypass the root logger).
        for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
            uv_logger = logging.getLogger(name)
            uv_logger.handlers.clear()
            uv_logger.propagate = True

        _CONFIGURED = True
    else:
        # Update existing handler levels on reconfiguration.
        for handler in root.handlers:
            handler.setLevel(level)


# ------------------------------------------------------------------
# Timed operation decorator
# ------------------------------------------------------------------


def timed_operation(fn: F) -> F:
    """Decorator that logs the wall-clock time of a function call.

    Works transparently with both synchronous and ``async`` functions.
    The elapsed time is logged at ``INFO`` level using the decorated
    function's module logger.

    Args:
        fn: The function (sync or async) to wrap.

    Returns:
        A wrapped version of *fn* that logs its execution time.
    """
    fn_logger = logging.getLogger(fn.__module__)

    if inspect.iscoroutinefunction(fn):

        @functools.wraps(fn)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            t0 = time.perf_counter()
            try:
                return await fn(*args, **kwargs)
            finally:
                elapsed = time.perf_counter() - t0
                fn_logger.info(
                    "%s completed in %.3fs",
                    fn.__name__,
                    elapsed,
                )

        return async_wrapper  # type: ignore[return-value]

    @functools.wraps(fn)
    def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
        t0 = time.perf_counter()
        try:
            return fn(*args, **kwargs)
        finally:
            elapsed = time.perf_counter() - t0
            fn_logger.info(
                "%s completed in %.3fs",
                fn.__name__,
                elapsed,
            )

    return sync_wrapper  # type: ignore[return-value]
