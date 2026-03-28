"""Tests for src/config.py — configuration validation utilities."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Required environment variables (must stay in sync with src/config.py)
# ---------------------------------------------------------------------------

ALL_REQUIRED_VARS = [
    "SCW_GENERATIVE_API_URL",
    "SCW_SECRET_KEY",
    "SCW_INFERENCE_ENDPOINT",
    "DATABASE_URL",
    "SCW_S3_ENDPOINT",
    "SCW_ACCESS_KEY",
    "SCW_S3_BUCKET",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _full_env() -> dict[str, str]:
    """Return an env dict with all required vars set to dummy values."""
    return {var: f"test-value-{var}" for var in ALL_REQUIRED_VARS}


# ---------------------------------------------------------------------------
# Tests: validate_config()
# ---------------------------------------------------------------------------

class TestValidateConfig:
    """Test the validate_config() function."""

    def test_passes_when_all_vars_set(self) -> None:
        """validate_config() must not raise when every required var is set."""
        from src.config import validate_config

        with patch.dict(os.environ, _full_env(), clear=True):
            # Should not raise
            validate_config()

    def test_raises_when_vars_missing(self) -> None:
        """validate_config() must raise EnvironmentError when vars are missing."""
        from src.config import validate_config

        # Clear all required vars
        env = {k: v for k, v in os.environ.items() if k not in ALL_REQUIRED_VARS}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(EnvironmentError):
                validate_config()

    def test_error_message_lists_all_missing_var_names(self) -> None:
        """The EnvironmentError message must include every missing var name."""
        from src.config import validate_config

        # Set only some vars — leave SCW_SECRET_KEY, DATABASE_URL, SCW_S3_BUCKET missing
        partial_env = {
            "SCW_GENERATIVE_API_URL": "https://example.com",
            "SCW_INFERENCE_ENDPOINT": "https://example.com",
            "SCW_S3_ENDPOINT": "https://example.com",
            "SCW_ACCESS_KEY": "key123",
        }
        missing = {"SCW_SECRET_KEY", "DATABASE_URL", "SCW_S3_BUCKET"}

        with patch.dict(os.environ, partial_env, clear=True):
            with pytest.raises(EnvironmentError, match="SCW_SECRET_KEY") as exc_info:
                validate_config()

            error_msg = str(exc_info.value)
            for var in missing:
                assert var in error_msg, (
                    f"Expected '{var}' in error message, got: {error_msg}"
                )

    def test_error_message_does_not_list_present_vars(self) -> None:
        """The error message must not mention vars that ARE set."""
        from src.config import validate_config

        # Set only SCW_GENERATIVE_API_URL
        partial_env = {"SCW_GENERATIVE_API_URL": "https://example.com"}

        with patch.dict(os.environ, partial_env, clear=True):
            with pytest.raises(EnvironmentError) as exc_info:
                validate_config()

            error_msg = str(exc_info.value)
            assert "SCW_GENERATIVE_API_URL" not in error_msg

    def test_accepts_required_vars_parameter(self) -> None:
        """validate_config() must accept custom required_vars for per-app use."""
        from src.config import validate_config

        # Only require a subset
        subset = ["SCW_GENERATIVE_API_URL", "SCW_SECRET_KEY"]
        env = {
            "SCW_GENERATIVE_API_URL": "https://example.com",
            "SCW_SECRET_KEY": "secret",
        }

        with patch.dict(os.environ, env, clear=True):
            # Should not raise when only the subset is required
            validate_config(required_vars=subset)

    def test_accepts_required_vars_raises_for_missing_subset(self) -> None:
        """validate_config(required_vars=...) must raise for missing subset vars."""
        from src.config import validate_config

        subset = ["SCW_GENERATIVE_API_URL", "SCW_SECRET_KEY"]

        with patch.dict(os.environ, {"SCW_GENERATIVE_API_URL": "ok"}, clear=True):
            with pytest.raises(EnvironmentError, match="SCW_SECRET_KEY"):
                validate_config(required_vars=subset)
