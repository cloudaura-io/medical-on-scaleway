"""Tests verifying sse-client.js lives in the shared static directory.

These tests ensure that the SSE client utility has been moved from the
Ambient Scribe showcase to the shared ``static/shared/`` directory at
the repository root, and that the old location no longer contains a copy.
"""

from __future__ import annotations

import importlib
import os
import sys
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

PROJECT_ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# Fixture: ambient scribe app
# ---------------------------------------------------------------------------

@pytest.fixture()
def client():
    """Return a TestClient for the ambient scribe app."""
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
# Tests: shared static file exists
# ---------------------------------------------------------------------------


class TestSharedSSEClientFile:
    """Verify that sse-client.js exists in the shared static directory."""

    def test_shared_sse_client_file_exists(self) -> None:
        """static/shared/sse-client.js must exist at the repo root."""
        shared_path = PROJECT_ROOT / "static" / "shared" / "sse-client.js"
        assert shared_path.is_file(), (
            f"Expected shared SSE client at {shared_path} but file does not exist"
        )

    def test_shared_sse_client_is_valid_js(self) -> None:
        """The shared sse-client.js must contain recognisable JS content."""
        shared_path = PROJECT_ROOT / "static" / "shared" / "sse-client.js"
        if not shared_path.is_file():
            pytest.skip("shared sse-client.js not yet created")
        content = shared_path.read_text()
        # Should contain the SSEClient export and core functions
        assert "SSEClient" in content
        assert "parseSSELines" in content

    def test_old_sse_client_removed_from_ambient_scribe(self) -> None:
        """01_ambient_scribe/static/sse-client.js must no longer exist."""
        old_path = PROJECT_ROOT / "01_ambient_scribe" / "static" / "sse-client.js"
        assert not old_path.exists(), (
            f"Old SSE client still exists at {old_path}; it should be removed"
        )


class TestSharedSSEClientServed:
    """Verify that the FastAPI app serves sse-client.js from the shared mount."""

    def test_shared_sse_client_served_via_http(self, client: TestClient) -> None:
        """GET /static/shared/sse-client.js must return 200 with JS content."""
        response = client.get("/static/shared/sse-client.js")
        assert response.status_code == 200
        assert "SSEClient" in response.text
