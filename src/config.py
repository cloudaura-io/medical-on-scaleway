"""
Shared configuration — Scaleway service clients.

Loads environment from .env and exposes pre-configured clients for:
- Generative APIs  (chat, STT, vision via OpenAI-compatible endpoint)
- Managed Inference (embeddings on dedicated GPU)
- PostgreSQL + pgvector
- S3 Object Storage
"""

import logging
import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Environment helpers
# ---------------------------------------------------------------------------


def _require(var: str) -> str:
    """Return an env var or raise with a clear message."""
    value = os.getenv(var)
    if not value:
        logger.error("Missing required environment variable: %s", var)
        raise OSError(f"Missing required environment variable: {var}")
    logger.debug("Loaded env var %s", var)
    return value


# All environment variables required for the full platform to operate.
ALL_REQUIRED_VARS: list[str] = [
    "SCW_GENERATIVE_API_URL",
    "SCW_SECRET_KEY",
    "SCW_INFERENCE_ENDPOINT",
    "SCW_VOXTRAL_REALTIME_ENDPOINT",
    "DATABASE_URL",
    "SCW_S3_ENDPOINT",
    "SCW_ACCESS_KEY",
    "SCW_S3_BUCKET",
]


def validate_config(
    required_vars: list[str] | None = None,
) -> None:
    """Check that all required environment variables are set.

    Call this at application startup — before creating any clients —
    so that missing configuration is surfaced immediately with a
    single, clear error message rather than failing on the first
    API call.

    Args:
        required_vars: An explicit list of env-var names to check.
            Defaults to :data:`ALL_REQUIRED_VARS` when *None*.

    Raises:
        EnvironmentError: If one or more required variables are unset
            or empty.  The error message lists every missing variable.
    """
    vars_to_check = required_vars if required_vars is not None else ALL_REQUIRED_VARS
    missing = [var for var in vars_to_check if not os.getenv(var)]

    if missing:
        names = ", ".join(missing)
        msg = f"Missing required environment variable(s): {names}. Set them in your .env file or shell environment."
        logger.error(msg)
        raise OSError(msg)


# ---------------------------------------------------------------------------
# OpenAI clients (lazily created so import alone never fails)
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def get_generative_client():
    """OpenAI client pointing at Scaleway Generative APIs.

    Used for chat completion, vision/OCR (Mistral Small 3.2), and STT (Voxtral).
    """
    from openai import OpenAI

    logger.info("Initialising generative API client")
    base_url = _require("SCW_GENERATIVE_API_URL")
    logger.debug("Generative API base_url=%s", base_url)
    return OpenAI(
        base_url=base_url,
        api_key=_require("SCW_SECRET_KEY"),
    )


def get_realtime_ws_url() -> str:
    """Return the WebSocket URL for the Voxtral Realtime vLLM endpoint.

    vLLM exposes a WebSocket at ``/v1/realtime`` for streaming audio
    transcription.  The env var ``SCW_VOXTRAL_REALTIME_ENDPOINT`` stores
    the HTTP base URL (e.g. ``http://host:8000/v1``); this function
    converts it to ``ws://host:8000/v1/realtime``.
    """
    base_url = _require("SCW_VOXTRAL_REALTIME_ENDPOINT")
    ws_url = base_url.replace("http://", "ws://").replace("https://", "wss://")
    ws_url = ws_url.rstrip("/")
    if not ws_url.endswith("/realtime"):
        ws_url += "/realtime"
    logger.debug("Voxtral Realtime WebSocket URL=%s", ws_url)
    return ws_url


@lru_cache(maxsize=1)
def get_inference_client():
    """OpenAI client pointing at a Managed Inference deployment.

    Dedicated GPU endpoint for BGE embeddings — keeps patient data
    on isolated infrastructure.
    """
    from openai import OpenAI

    logger.info("Initialising managed inference client")
    base_url = _require("SCW_INFERENCE_ENDPOINT")
    logger.debug("Inference endpoint base_url=%s", base_url)
    return OpenAI(
        base_url=base_url,
        api_key=_require("SCW_SECRET_KEY"),
    )


# ---------------------------------------------------------------------------
# PostgreSQL
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def get_db_connection():
    """Return a psycopg connection (auto-commit) to the pgvector database."""
    import psycopg

    logger.info("Initialising PostgreSQL connection")
    conn = psycopg.connect(_require("DATABASE_URL"), autocommit=True)
    conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    logger.info("PostgreSQL connection established, pgvector extension ensured")
    return conn


# ---------------------------------------------------------------------------
# S3 / Object Storage
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def get_s3_client():
    """Boto3 S3 client configured for Scaleway Object Storage."""
    import boto3

    logger.info("Initialising S3 client")
    endpoint_url = _require("SCW_S3_ENDPOINT")
    logger.debug("S3 endpoint_url=%s", endpoint_url)
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=_require("SCW_ACCESS_KEY"),
        aws_secret_access_key=_require("SCW_SECRET_KEY"),
        region_name="fr-par",
    )


def get_s3_bucket() -> str:
    """Return the configured bucket name."""
    bucket = _require("SCW_S3_BUCKET")
    logger.debug("Using S3 bucket=%s", bucket)
    return bucket


# ---------------------------------------------------------------------------
# Model constants (single source of truth)
# ---------------------------------------------------------------------------

CHAT_MODEL = "mistral-small-3.2-24b-instruct-2506"  # also handles vision/OCR
STT_MODEL = "voxtral-small-24b-2507"
VISION_MODEL = CHAT_MODEL  # pixtral-12b-2409 is deprecated; Mistral Small 3.2 has native vision
EMBEDDING_MODEL = "bge-multilingual-gemma2"
REALTIME_STT_MODEL = "Voxtral-Mini-4B-Realtime-2602"
