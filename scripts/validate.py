#!/usr/bin/env python3
"""
Validate all infrastructure components.

Checks connectivity and basic functionality of:
  - Scaleway Generative APIs (chat model)
  - Scaleway Managed Inference (embedding model)
  - PostgreSQL + pgvector
  - S3 Object Storage

Usage:
    python scripts/validate.py
    python scripts/validate.py --verbose
"""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

# ─────────────────────────────────────────────────────────────────────────────

RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
NC = "\033[0m"

VERBOSE = False
results: list[tuple[str, bool, str]] = []


def check(name: str):
    """Decorator that catches exceptions and records pass/fail."""

    def decorator(func):
        def wrapper():
            try:
                detail = func()
                results.append((name, True, detail or "OK"))
                print(f"  {GREEN}✓{NC} {name}: {detail or 'OK'}")
            except Exception as e:
                msg = str(e)
                if VERBOSE:
                    import traceback

                    msg = traceback.format_exc()
                results.append((name, False, msg))
                print(f"  {RED}✗{NC} {name}: {msg}")

        return wrapper

    return decorator


# ─────────────────────────────────────────────────────────────────────────────
# Checks
# ─────────────────────────────────────────────────────────────────────────────


@check("Generative APIs (chat)")
def check_generative_api():
    from src.config import CHAT_MODEL, get_generative_client

    client = get_generative_client()
    resp = client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[{"role": "user", "content": "Say OK"}],
        max_tokens=5,
    )
    content = resp.choices[0].message.content.strip()
    return f'{CHAT_MODEL} -> "{content}"'


@check("Generative APIs (STT model available)")
def check_stt_model():
    from src.config import STT_MODEL, get_generative_client

    client = get_generative_client()
    models = client.models.list()
    found = any(m.id == STT_MODEL for m in models.data)
    if not found:
        raise RuntimeError(f"Model {STT_MODEL} not found in available models")
    return f"{STT_MODEL} available"


@check("Generative APIs (vision model available)")
def check_vision_model():
    from src.config import VISION_MODEL, get_generative_client

    client = get_generative_client()
    models = client.models.list()
    found = any(m.id == VISION_MODEL for m in models.data)
    if not found:
        raise RuntimeError(f"Model {VISION_MODEL} not found in available models")
    return f"{VISION_MODEL} available"


@check("Managed Inference (embeddings)")
def check_inference():
    from src.config import EMBEDDING_MODEL, get_inference_client

    client = get_inference_client()
    resp = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input="test",
    )
    dim = len(resp.data[0].embedding)
    return f"{EMBEDDING_MODEL} -> {dim}-dim embedding"


@check("PostgreSQL connection")
def check_db_connection():
    from src.config import get_db_connection

    conn = get_db_connection()
    version = conn.execute("SELECT version()").fetchone()[0]
    short = version.split(",")[0]
    return short


@check("pgvector extension")
def check_pgvector():
    from src.config import get_db_connection

    conn = get_db_connection()
    row = conn.execute("SELECT extversion FROM pg_extension WHERE extname = 'vector'").fetchone()
    if not row:
        raise RuntimeError("pgvector extension not installed")
    return f"v{row[0]}"


@check("Database tables")
def check_tables():
    from src.config import get_db_connection

    conn = get_db_connection()
    rows = conn.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename").fetchall()
    tables = [r[0] for r in rows]
    if not tables:
        raise RuntimeError("No tables found in public schema")
    return ", ".join(tables)


@check("Knowledge base chunks")
def check_knowledge_chunks():
    from src.config import get_db_connection

    conn = get_db_connection()
    # Check if document_chunks table exists
    exists = conn.execute("SELECT EXISTS (SELECT 1 FROM pg_tables WHERE tablename = 'document_chunks')").fetchone()[0]
    if not exists:
        raise RuntimeError("document_chunks table not found")

    count = conn.execute("SELECT COUNT(*) FROM document_chunks").fetchone()[0]
    if count == 0:
        raise RuntimeError("No chunks loaded — run load-knowledge-base.py")

    domains = conn.execute("SELECT domain, COUNT(*) FROM document_chunks GROUP BY domain ORDER BY domain").fetchall()
    domain_str = ", ".join(f"{d[0]}({d[1]})" for d in domains)
    return f"{count} chunks [{domain_str}]"


@check("S3 Object Storage")
def check_s3():
    from src.config import get_s3_bucket, get_s3_client

    client = get_s3_client()
    bucket = get_s3_bucket()
    # List bucket to verify access (empty bucket is fine)
    resp = client.list_objects_v2(Bucket=bucket, MaxKeys=1)
    count = resp.get("KeyCount", 0)
    return f"bucket '{bucket}' accessible ({count} objects)"


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────


def main():
    global VERBOSE

    parser = argparse.ArgumentParser(description="Validate infrastructure setup")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show full tracebacks")
    args = parser.parse_args()
    VERBOSE = args.verbose

    print("\nValidating Scaleway Medical AI Lab infrastructure:\n")

    check_generative_api()
    check_stt_model()
    check_vision_model()
    check_inference()
    check_db_connection()
    check_pgvector()
    check_tables()
    check_knowledge_chunks()
    check_s3()

    passed = sum(1 for _, ok, _ in results if ok)
    failed = sum(1 for _, ok, _ in results if not ok)

    print(f"\n{'─' * 60}")
    print(f"  {GREEN}{passed} passed{NC}", end="")
    if failed:
        print(f"  {RED}{failed} failed{NC}", end="")
    print()

    if failed:
        print(f"\n{YELLOW}Failing checks:{NC}")
        for name, ok, detail in results:
            if not ok:
                print(f"  - {name}: {detail}")
        sys.exit(1)


if __name__ == "__main__":
    main()
