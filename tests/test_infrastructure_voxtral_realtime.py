"""Tests for infrastructure - Voxtral Realtime GPU instance resources."""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INFRA_DIR = PROJECT_ROOT / "infrastructure"


class TestVoxtralRealtimeInfrastructure:
    """Verify that OpenTofu config includes Voxtral Realtime GPU instance."""

    def test_main_tf_contains_gpu_instance(self) -> None:
        """main.tf must define a GPU instance for vLLM."""
        content = (INFRA_DIR / "main.tf").read_text()
        assert "scaleway_instance_server" in content
        assert "voxtral_gpu" in content
        assert "L4-1-24G" in content

    def test_main_tf_contains_security_group(self) -> None:
        """main.tf must define a security group for the GPU instance."""
        content = (INFRA_DIR / "main.tf").read_text()
        assert "scaleway_instance_security_group" in content
        assert "8000" in content  # vLLM port

    def test_main_tf_references_cloud_init(self) -> None:
        """main.tf must use the cloud-init file for vLLM setup."""
        content = (INFRA_DIR / "main.tf").read_text()
        assert "cloud-init-vllm.yaml" in content

    def test_cloud_init_exists_and_configures_vllm(self) -> None:
        """cloud-init-vllm.yaml must exist and configure vLLM with Voxtral."""
        cloud_init = INFRA_DIR / "cloud-init-vllm.yaml"
        assert cloud_init.exists(), "cloud-init-vllm.yaml not found"
        content = cloud_init.read_text()
        assert "vllm" in content
        assert "Voxtral-Mini-4B-Realtime-2602" in content
        assert "docker" in content.lower()

    def test_outputs_include_voxtral_realtime_endpoint(self) -> None:
        """outputs.tf must expose the vLLM endpoint URL."""
        content = (INFRA_DIR / "outputs.tf").read_text()
        assert "voxtral_realtime_endpoint" in content
        assert "8000" in content

    def test_env_example_includes_voxtral_realtime(self) -> None:
        """.env.example must document SCW_VOXTRAL_REALTIME_ENDPOINT."""
        content = (PROJECT_ROOT / ".env.example").read_text()
        assert "SCW_VOXTRAL_REALTIME_ENDPOINT" in content
