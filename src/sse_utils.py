"""
Shared SSE (Server-Sent Events) formatting and streaming utilities.

Provides a unified API for producing consistent SSE output across all
showcase applications, plus an error-handling wrapper for async
generators that stream SSE events.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# SSE formatting
# ------------------------------------------------------------------


def format_sse_event(event: str, data: dict[str, Any]) -> str:
    """Format a dict as an SSE ``data:`` line.

    The *event* name is merged into *data* under the ``"event"`` key
    so the client can dispatch on a single field.  The output follows
    the standard SSE wire format::

        data: {"event": "<event>", ...}\n\n

    Args:
        event: A short event name (e.g. ``"progress"``, ``"error"``).
        data: Arbitrary JSON-serialisable payload.

    Returns:
        A string ready to be yielded from a ``StreamingResponse``.
    """
    payload = {"event": event, **data}
    return f"data: {json.dumps(payload)}\n\n"


# ------------------------------------------------------------------
# Streaming error wrapper
# ------------------------------------------------------------------


async def safe_streaming_wrapper(
    generator: AsyncIterator[str],
) -> AsyncIterator[str]:
    """Wrap an async generator so exceptions become SSE error events.

    Any exception raised inside *generator* is caught and converted
    into a standardised error SSE event using :func:`format_sse_event`.
    This prevents the HTTP connection from dropping silently on the
    client side.

    Args:
        generator: An async iterator that yields SSE-formatted strings.

    Yields:
        SSE-formatted strings — either from the original generator or
        a synthesised error event.
    """
    try:
        async for event in generator:
            yield event
    except Exception as exc:
        logger.error(
            "Streaming error caught by safe_streaming_wrapper: %s",
            exc,
            exc_info=True,
        )
        yield format_sse_event("error", {"detail": str(exc)})
