"""Tests for src/app_factory.py - shared FastAPI setup utilities."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def static_dir(tmp_path: Path) -> Path:
    """Create a temp directory with a minimal index.html."""
    index_html = tmp_path / "index.html"
    index_html.write_text("<html><body><h1>Test App</h1></body></html>")
    return tmp_path


# ---------------------------------------------------------------------------
# Tests: setup_project_path()
# ---------------------------------------------------------------------------


class TestSetupProjectPath:
    """Test the setup_project_path() helper."""

    def test_returns_project_root(self, tmp_path: Path) -> None:
        """setup_project_path() must return the grandparent of the file."""
        from src.app_factory import setup_project_path

        # Simulate a file at <root>/app_dir/main.py
        app_dir = tmp_path / "my_app"
        app_dir.mkdir()
        fake_main = app_dir / "main.py"
        fake_main.touch()

        result = setup_project_path(str(fake_main))
        assert result == tmp_path

    def test_adds_root_to_sys_path(self, tmp_path: Path) -> None:
        """setup_project_path() must add project root to sys.path."""
        from src.app_factory import setup_project_path

        app_dir = tmp_path / "my_app"
        app_dir.mkdir()
        fake_main = app_dir / "main.py"
        fake_main.touch()

        # Remove if already present to test the insert
        root_str = str(tmp_path)
        original_path = sys.path.copy()
        try:
            while root_str in sys.path:
                sys.path.remove(root_str)
            setup_project_path(str(fake_main))
            assert root_str in sys.path
        finally:
            sys.path[:] = original_path

    def test_does_not_duplicate_path(self, tmp_path: Path) -> None:
        """setup_project_path() must not duplicate an existing entry."""
        from src.app_factory import setup_project_path

        app_dir = tmp_path / "my_app"
        app_dir.mkdir()
        fake_main = app_dir / "main.py"
        fake_main.touch()

        root_str = str(tmp_path)
        original_path = sys.path.copy()
        try:
            # Ensure root is already present
            if root_str not in sys.path:
                sys.path.insert(0, root_str)
            count_before = sys.path.count(root_str)
            setup_project_path(str(fake_main))
            count_after = sys.path.count(root_str)
            assert count_after == count_before
        finally:
            sys.path[:] = original_path


# ---------------------------------------------------------------------------
# Tests: create_app()
# ---------------------------------------------------------------------------


class TestCreateApp:
    """Test the create_app() factory function."""

    def test_returns_fastapi_instance(self) -> None:
        """create_app() must return a FastAPI instance."""
        from src.app_factory import create_app

        app = create_app(title="Test App", version="0.1.0")
        assert isinstance(app, FastAPI)

    def test_sets_title_and_version(self) -> None:
        """create_app() must set the title and version on the app."""
        from src.app_factory import create_app

        app = create_app(title="My Title", version="2.0.0")
        assert app.title == "My Title"
        assert app.version == "2.0.0"

    def test_cors_middleware_configured(self) -> None:
        """create_app() must add CORS middleware with allow_origins=['*']."""
        from src.app_factory import create_app

        app = create_app(title="Test", version="0.1.0")

        # Verify CORS middleware is present by checking middleware stack
        middleware_classes = [m.cls.__name__ for m in app.user_middleware]
        assert "CORSMiddleware" in middleware_classes


# ---------------------------------------------------------------------------
# Tests: mount_static()
# ---------------------------------------------------------------------------


class TestMountStatic:
    """Test the mount_static() helper."""

    def test_mounts_static_directory(self, static_dir: Path) -> None:
        """mount_static() must mount files so they are accessible."""
        from src.app_factory import create_app, mount_static

        app = create_app(title="Test", version="0.1.0")
        mount_static(app, static_dir)

        client = TestClient(app)
        resp = client.get("/static/index.html")
        assert resp.status_code == 200
        assert "Test App" in resp.text


# ---------------------------------------------------------------------------
# Tests: create_index_route()
# ---------------------------------------------------------------------------


class TestCreateIndexRoute:
    """Test the create_index_route() helper."""

    def test_serves_index_html(self, static_dir: Path) -> None:
        """GET / must return the content of index.html."""
        from src.app_factory import (
            create_app,
            create_index_route,
            mount_static,
        )

        app = create_app(title="Test", version="0.1.0")
        mount_static(app, static_dir)
        create_index_route(app, static_dir)

        client = TestClient(app)
        resp = client.get("/")
        assert resp.status_code == 200
        assert "<h1>Test App</h1>" in resp.text


# ---------------------------------------------------------------------------
# Tests: create_health_endpoint()
# ---------------------------------------------------------------------------


class TestCreateHealthEndpoint:
    """Test the create_health_endpoint() helper."""

    def test_returns_status_ok(self) -> None:
        """GET /api/health must include status 'ok'."""
        from src.app_factory import create_app, create_health_endpoint

        app = create_app(title="Test", version="0.1.0")
        create_health_endpoint(app)

        client = TestClient(app)
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    def test_includes_custom_fields(self) -> None:
        """GET /api/health must include any extra keyword arguments."""
        from src.app_factory import create_app, create_health_endpoint

        app = create_app(title="Test", version="0.1.0")
        create_health_endpoint(app, model="test-model", domains=3)

        client = TestClient(app)
        resp = client.get("/api/health")
        data = resp.json()
        assert data["model"] == "test-model"
        assert data["domains"] == 3

    def test_custom_fields_callable(self) -> None:
        """GET /api/health must evaluate callable custom fields."""
        from src.app_factory import create_app, create_health_endpoint

        counter = {"value": 0}

        def get_count() -> int:
            counter["value"] += 1
            return counter["value"]

        app = create_app(title="Test", version="0.1.0")
        create_health_endpoint(app, count=get_count)

        client = TestClient(app)
        resp1 = client.get("/api/health")
        resp2 = client.get("/api/health")
        assert resp1.json()["count"] == 1
        assert resp2.json()["count"] == 2
