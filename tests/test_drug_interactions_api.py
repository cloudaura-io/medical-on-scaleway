"""Tests for the Drug Interactions API endpoints (03_drug_interactions/main.py)."""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

_project_root = str(Path(__file__).resolve().parents[1])
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


# ---------------------------------------------------------------------------
# Fixture: drug interactions app
# ---------------------------------------------------------------------------


@pytest.fixture()
def client():
    """Return a TestClient for the drug interactions app."""
    env_patch = patch.dict(
        os.environ,
        {
            "SCW_GENERATIVE_API_URL": "https://fake.api",
            "SCW_SECRET_KEY": "fake-key",
            "SCW_INFERENCE_ENDPOINT": "https://fake.inference",
            "DATABASE_URL": "postgresql://fake:fake@localhost:5432/fake",
        },
    )
    env_patch.start()

    from src.config import get_generative_client, get_inference_client

    get_generative_client.cache_clear()
    get_inference_client.cache_clear()

    # Remove cached module if present
    mod_name = "03_drug_interactions.main"
    if mod_name in sys.modules:
        del sys.modules[mod_name]

    importlib.invalidate_caches()

    from importlib import import_module

    drug_app_mod = import_module("03_drug_interactions.main")
    yield TestClient(drug_app_mod.app)

    env_patch.stop()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestHealthEndpoint:
    """Test GET /api/health."""

    def test_returns_200(self, client: TestClient) -> None:
        """GET /api/health returns 200 with status ok."""
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_includes_model(self, client: TestClient) -> None:
        """GET /api/health includes model field."""
        response = client.get("/api/health")
        data = response.json()
        assert "model" in data


class TestSampleQueries:
    """Test GET /api/sample-queries."""

    def test_returns_sample_combinations(self, client: TestClient) -> None:
        """GET /api/sample-queries returns a list of sample medication combos."""
        response = client.get("/api/sample-queries")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 3

    def test_sample_structure(self, client: TestClient) -> None:
        """Each sample query has medications and optional population."""
        response = client.get("/api/sample-queries")
        data = response.json()
        for sample in data:
            assert "medications" in sample
            assert isinstance(sample["medications"], list)
            assert len(sample["medications"]) >= 2


class TestAnalyzeEndpoint:
    """Test POST /api/analyze."""

    def test_invalid_input_returns_422(self, client: TestClient) -> None:
        """POST /api/analyze with empty medications returns 400."""
        response = client.post(
            "/api/analyze",
            json={"medications": []},
        )
        assert response.status_code == 400

    def test_missing_medications_returns_422(self, client: TestClient) -> None:
        """POST /api/analyze without medications field returns 400."""
        response = client.post(
            "/api/analyze",
            json={},
        )
        assert response.status_code == 400


class TestIndexRoute:
    """Test GET / serves index.html."""

    def test_serves_html(self, client: TestClient) -> None:
        """GET / returns HTML content."""
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
