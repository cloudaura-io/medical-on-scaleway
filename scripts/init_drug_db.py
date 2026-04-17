"""Initialize the drug interaction knowledge base.

Reads FDA drug labels from workshop/data/openfda_labels.json, chunks them
by section type, generates 768-dim embeddings via Qwen3 Embedding on
Scaleway Generative APIs, and bulk-inserts into the drug_chunks pgvector table.

Idempotent: drops and recreates the drug_chunks table on each run.

Usage:
    python scripts/init_drug_db.py [--data-path workshop/data/openfda_labels.json]
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

# Project path setup
_project_root = str(Path(__file__).resolve().parents[1])
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from src.drug_chunker import chunk_label
from src.drug_rag import CREATE_INDEX_SQL, CREATE_TABLE_SQL, insert_drug_chunks

logger = logging.getLogger(__name__)

DEFAULT_DATA_PATH = str(Path(_project_root) / "workshop" / "data" / "openfda_labels.json")
DEFAULT_BATCH_SIZE = 32

DROP_TABLE_SQL = "DROP TABLE IF EXISTS drug_chunks;"


# ---------------------------------------------------------------------------
# Public API (importable for testing)
# ---------------------------------------------------------------------------


def load_labels(data_path: str) -> list[dict[str, Any]]:
    """Load openFDA labels from a JSON file.

    Args:
        data_path: Path to the openfda_labels.json file.

    Returns:
        List of label dicts.
    """
    with open(data_path) as f:
        labels = json.load(f)
    logger.info("Loaded %d labels from %s", len(labels), data_path)
    return labels


def chunk_all_labels(labels: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Chunk all labels into section-typed chunks.

    Args:
        labels: List of openFDA label dicts.

    Returns:
        Flat list of chunk dicts.
    """
    all_chunks: list[dict[str, Any]] = []
    for label in labels:
        chunks = chunk_label(label)
        all_chunks.extend(chunks)
    logger.info("Chunked %d labels into %d chunks", len(labels), len(all_chunks))
    return all_chunks


def seed_database(
    conn: Any,
    embeddings_client: Any,
    chunks: list[dict[str, Any]],
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> int:
    """Drop, recreate, and populate the drug_chunks table.

    Args:
        conn: A psycopg connection object.
        embeddings_client: An EmbeddingsClient for generating embeddings.
        chunks: List of chunk dicts (without embeddings).
        batch_size: Number of texts to embed in a single API call.

    Returns:
        Total number of chunks inserted.
    """
    # Drop and recreate table with HNSW index (idempotent)
    with conn.cursor() as cur:
        cur.execute(DROP_TABLE_SQL)
        cur.execute(CREATE_TABLE_SQL)
        cur.execute(CREATE_INDEX_SQL)
    conn.commit()
    logger.info("Dropped and recreated drug_chunks table")

    # Process in batches
    total_inserted = 0
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        texts = [c["text"] for c in batch]

        t0 = time.perf_counter()
        embeddings = embeddings_client.embed_batch(texts)
        elapsed = time.perf_counter() - t0

        # Attach embeddings to chunks
        for chunk, embedding in zip(batch, embeddings, strict=True):
            chunk["embedding"] = embedding

        insert_drug_chunks(conn, batch)
        total_inserted += len(batch)

        logger.info(
            "Batch %d-%d: embedded %d chunks in %.1fs, total=%d/%d",
            i + 1,
            i + len(batch),
            len(batch),
            elapsed,
            total_inserted,
            len(chunks),
        )

    logger.info("Seeding complete: %d chunks inserted", total_inserted)
    return total_inserted


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI entrypoint for database initialization."""
    parser = argparse.ArgumentParser(description="Initialize the drug interaction knowledge base")
    parser.add_argument(
        "--data-path",
        default=DEFAULT_DATA_PATH,
        help="Path to openfda_labels.json",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help="Number of texts to embed per API call",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    from src.config import EMBEDDING_DIMENSIONS, EMBEDDING_MODEL, get_db_connection, get_generative_client
    from src.drug_embeddings import EmbeddingsClient

    logger.info("Initializing drug interaction knowledge base...")

    # Load and chunk
    labels = load_labels(args.data_path)
    chunks = chunk_all_labels(labels)

    # Set up clients -- use Generative APIs (serverless) for Qwen3 embeddings
    conn = get_db_connection()
    gen_client = get_generative_client()
    embeddings_client = EmbeddingsClient(
        client=gen_client,
        model=EMBEDDING_MODEL,
        dimensions=EMBEDDING_DIMENSIONS,
    )

    # Seed
    total = seed_database(conn, embeddings_client, chunks, batch_size=args.batch_size)
    logger.info("Done! Inserted %d chunks into drug_chunks table.", total)


if __name__ == "__main__":
    main()
