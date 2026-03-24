"""
Shared configuration — Scaleway service clients.

Loads environment from .env and exposes pre-configured clients for:
- Generative APIs  (chat, STT, vision via OpenAI-compatible endpoint)
- Managed Inference (embeddings on dedicated GPU)
- PostgreSQL + pgvector
- S3 Object Storage
"""

import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Environment helpers
# ---------------------------------------------------------------------------

def _require(var: str) -> str:
    """Return an env var or raise with a clear message."""
    value = os.getenv(var)
    if not value:
        raise EnvironmentError(f"Missing required environment variable: {var}")
    return value


# ---------------------------------------------------------------------------
# OpenAI clients (lazily created so import alone never fails)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def get_generative_client():
    """OpenAI client pointing at Scaleway Generative APIs.

    Used for chat completion (Mistral), STT (Voxtral), vision (Pixtral).
    """
    from openai import OpenAI

    return OpenAI(
        base_url=_require("SCW_GENERATIVE_API_URL"),
        api_key=_require("SCW_SECRET_KEY"),
    )


@lru_cache(maxsize=1)
def get_inference_client():
    """OpenAI client pointing at a Managed Inference deployment.

    Dedicated GPU endpoint for BGE embeddings — keeps patient data
    on isolated infrastructure.
    """
    from openai import OpenAI

    return OpenAI(
        base_url=_require("SCW_INFERENCE_ENDPOINT"),
        api_key=_require("SCW_SECRET_KEY"),
    )


# ---------------------------------------------------------------------------
# PostgreSQL
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def get_db_connection():
    """Return a psycopg connection (auto-commit) to the pgvector database."""
    import psycopg

    conn = psycopg.connect(_require("DATABASE_URL"), autocommit=True)
    # Ensure the pgvector extension and required tables exist.
    conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    return conn


# ---------------------------------------------------------------------------
# S3 / Object Storage
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def get_s3_client():
    """Boto3 S3 client configured for Scaleway Object Storage."""
    import boto3

    return boto3.client(
        "s3",
        endpoint_url=_require("SCW_S3_ENDPOINT"),
        aws_access_key_id=_require("SCW_ACCESS_KEY"),
        aws_secret_access_key=_require("SCW_SECRET_KEY"),
        region_name="fr-par",
    )


def get_s3_bucket() -> str:
    """Return the configured bucket name."""
    return _require("SCW_S3_BUCKET")


# ---------------------------------------------------------------------------
# Model constants (single source of truth)
# ---------------------------------------------------------------------------

CHAT_MODEL = "mistral-small-3.2-24b-instruct-2506"
STT_MODEL = "voxtral-small-24b-2507"
VISION_MODEL = "pixtral-12b-2409"
EMBEDDING_MODEL = "bge-multilingual-gemma2"
