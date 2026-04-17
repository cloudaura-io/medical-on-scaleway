"""
Shared FastAPI application factory and setup utilities.

Provides reusable helpers so each showcase app can initialise
FastAPI with consistent CORS, static file mounting, health
checks, and index routes - without duplicating boilerplate.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Project path setup
# ------------------------------------------------------------------


def setup_project_path(caller_file: str) -> Path:
    """Ensure the project root is on ``sys.path``.

    Call this from each app's ``main.py`` with ``__file__`` so that
    ``from src.…`` imports work regardless of the working directory.

    Args:
        caller_file: The ``__file__`` attribute of the calling module
            (must be inside a direct subdirectory of the project root).

    Returns:
        The resolved project root ``Path``.
    """
    project_root = Path(caller_file).resolve().parents[1]
    root_str = str(project_root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
    logger.debug("Project root on sys.path: %s", root_str)
    return project_root


# ------------------------------------------------------------------
# App creation
# ------------------------------------------------------------------


def create_app(title: str, version: str) -> FastAPI:
    """Create a FastAPI instance with standard CORS middleware.

    Args:
        title: Application title shown in the OpenAPI docs.
        version: Semantic version string.

    Returns:
        A fully configured FastAPI application.
    """
    app = FastAPI(title=title, version=version)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    logger.info("Created FastAPI app: %s v%s", title, version)
    return app


# ------------------------------------------------------------------
# Static file mounting
# ------------------------------------------------------------------


def mount_static(app: FastAPI, static_dir: Path) -> None:
    """Mount a directory of static assets at ``/static``.

    Args:
        app: The FastAPI application instance.
        static_dir: Path to the directory containing static files.
    """
    app.mount(
        "/static",
        StaticFiles(directory=str(static_dir)),
        name="static",
    )
    logger.info("Mounted static files from %s", static_dir)


def mount_shared_static(app: FastAPI, project_root: Path) -> None:
    """Mount the repo-wide ``static/shared`` directory at ``/static/shared``.

    MUST be called BEFORE :func:`mount_static` so that FastAPI's static file
    router matches the more-specific ``/static/shared`` path before falling
    through to the per-showcase ``/static`` mount.

    Args:
        app: The FastAPI application instance.
        project_root: The repository root (where ``static/shared`` lives).
    """
    shared_dir = project_root / "static" / "shared"
    app.mount(
        "/static/shared",
        StaticFiles(directory=str(shared_dir)),
        name="shared_static",
    )
    logger.info("Mounted shared static files from %s", shared_dir)


# ------------------------------------------------------------------
# Index route
# ------------------------------------------------------------------


def create_index_route(app: FastAPI, static_dir: Path) -> None:
    """Register a ``GET /`` route that serves ``index.html``.

    Args:
        app: The FastAPI application instance.
        static_dir: Path to the directory containing index.html.
    """
    html_path = static_dir / "index.html"

    @app.get("/", response_class=HTMLResponse)
    async def index() -> HTMLResponse:
        """Serve the single-page frontend."""
        return HTMLResponse(content=html_path.read_text(), status_code=200)

    logger.info("Registered index route serving %s", html_path)


# ------------------------------------------------------------------
# Health endpoint
# ------------------------------------------------------------------


def create_health_endpoint(
    app: FastAPI,
    **custom_fields: Any,
) -> None:
    """Register a ``GET /api/health`` endpoint.

    The endpoint always returns ``{"status": "ok", ...}``.  Extra
    keyword arguments are included in the response.  If a value is
    callable it will be invoked on each request so that dynamic
    fields (e.g. document counts) stay up to date.

    Args:
        app: The FastAPI application instance.
        **custom_fields: Additional key-value pairs to include in
            the health response.  Callable values are evaluated
            per request.
    """

    @app.get("/api/health")
    async def health() -> dict:
        """Return service health status."""
        result: dict[str, Any] = {"status": "ok"}
        for key, value in custom_fields.items():
            result[key] = value() if callable(value) else value
        return result

    logger.info(
        "Registered health endpoint with fields: %s",
        list(custom_fields.keys()),
    )
