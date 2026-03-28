"""
Tests for dead code and stale references in 01_ambient_scribe/main.py.

Verifies that all imports in main.py are actually used in the module body,
catching leftover imports from previous refactors (e.g., SSE streaming removal).

Run: python -m pytest 01_ambient_scribe/test_main_imports.py -v
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

MAIN_PY = Path(__file__).parent / "main.py"


def _read_source() -> str:
    """Return the source code of main.py as a string."""
    return MAIN_PY.read_text(encoding="utf-8")


def _get_imported_names(source: str) -> list[str]:
    """Extract all imported names from the module source using AST parsing.

    Returns a list of (name, lineno) tuples for every name brought into scope
    via ``import X`` or ``from X import Y`` statements.
    """
    tree = ast.parse(source)
    names: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                bound = alias.asname if alias.asname else alias.name.split(".")[0]
                names.append((bound, node.lineno))
        elif isinstance(node, ast.ImportFrom):
            # Skip __future__ imports — they are compiler directives, not runtime imports
            if node.module == "__future__":
                continue
            for alias in node.names:
                bound = alias.asname if alias.asname else alias.name
                names.append((bound, node.lineno))
    return names


def _name_used_outside_import(name: str, source: str) -> bool:
    """Check whether *name* appears in the source outside its own import line.

    A simple heuristic: count occurrences of the name as a whole word.
    If it appears more than once (the import itself), it is used.
    """
    pattern = re.compile(rf"\b{re.escape(name)}\b")
    matches = pattern.findall(source)
    # The import statement accounts for at least one occurrence.
    return len(matches) > 1


class TestMainImports:
    """Verify that every import in main.py is actually used."""

    source = _read_source()
    imported = _get_imported_names(source)

    @pytest.mark.parametrize(
        "name,lineno",
        imported,
        ids=[f"{n} (line {l})" for n, l in _get_imported_names(_read_source())],
    )
    def test_import_is_used(self, name: str, lineno: int) -> None:
        """Import '{name}' on line {lineno} must be referenced elsewhere in main.py."""
        assert _name_used_outside_import(name, self.source), (
            f"Import '{name}' (line {lineno}) appears unused in main.py — "
            f"remove if it is dead code"
        )


class TestNoStaleReferences:
    """Verify that main.py does not contain stale references to removed code."""

    source = _read_source()

    def test_no_sse_starlette_import(self) -> None:
        """main.py must not import sse-starlette (no longer used by this showcase)."""
        assert "sse_starlette" not in self.source, (
            "main.py should not reference sse_starlette — "
            "SSE streaming was removed in favor of diarized transcription"
        )

    def test_no_httpx_import(self) -> None:
        """main.py must not import httpx (no longer used by this showcase)."""
        assert "httpx" not in self.source, (
            "main.py should not reference httpx — "
            "it was only needed for the SSE streaming approach"
        )

    def test_no_transcribe_stream_endpoint(self) -> None:
        """main.py must not define a /api/transcribe-stream endpoint."""
        assert "transcribe-stream" not in self.source, (
            "main.py should not define /api/transcribe-stream — "
            "the streaming endpoint was replaced by /api/transcribe"
        )

    def test_no_transcribe_audio_stream_function(self) -> None:
        """main.py must not reference the removed transcribe_audio_stream function."""
        assert "transcribe_audio_stream" not in self.source, (
            "main.py should not reference transcribe_audio_stream — "
            "it was replaced by transcribe_audio_diarized"
        )
