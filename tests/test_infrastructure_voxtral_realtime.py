"""Tests for infrastructure — Voxtral Realtime deployment resources."""

from __future__ import annotations

from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INFRA_DIR = PROJECT_ROOT / "infrastructure"


class TestVoxtralRealtimeInfrastructure:
    """Verify that OpenTofu config includes Voxtral Realtime resources."""

    def test_main_tf_contains_inference_model_import(self) -> None:
        """main.tf must import voxtral-mini-4b-realtime from HuggingFace."""
        content = (INFRA_DIR / "main.tf").read_text()
        assert 'scaleway_inference_model' in content
        assert 'voxtral_realtime' in content
        assert 'Voxtral-Mini-4B-Realtime-2602' in content

    def test_main_tf_contains_deployment_resource(self) -> None:
        """main.tf must define a deployment for the Voxtral Realtime model."""
        content = (INFRA_DIR / "main.tf").read_text()
        assert 'scaleway_inference_deployment' in content
        assert '"voxtral_realtime"' in content or "'voxtral_realtime'" in content
        assert 'node_type' in content

    def test_outputs_include_voxtral_realtime_endpoint(self) -> None:
        """outputs.tf must expose the Voxtral Realtime endpoint URL."""
        content = (INFRA_DIR / "outputs.tf").read_text()
        assert 'voxtral_realtime_endpoint' in content
        assert 'voxtral_realtime' in content

    def test_generate_env_includes_voxtral_realtime(self) -> None:
        """generate-env.sh must read and write SCW_VOXTRAL_REALTIME_ENDPOINT."""
        content = (PROJECT_ROOT / "scripts" / "generate-env.sh").read_text()
        assert 'VOXTRAL_REALTIME_ENDPOINT' in content
        assert 'voxtral_realtime_endpoint' in content

    def test_env_example_includes_voxtral_realtime(self) -> None:
        """.env.example must document SCW_VOXTRAL_REALTIME_ENDPOINT."""
        content = (PROJECT_ROOT / ".env.example").read_text()
        assert 'SCW_VOXTRAL_REALTIME_ENDPOINT' in content
