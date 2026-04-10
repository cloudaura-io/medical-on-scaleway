#!/usr/bin/env python3
"""
Load knowledge base documents into pgvector.

Reads all Markdown files from data/knowledge_base/, chunks them,
generates embeddings via Managed Inference (BGE), and stores
them in the PostgreSQL database for RAG retrieval.

Usage:
    python scripts/load-knowledge-base.py
    python scripts/load-knowledge-base.py --dry-run
    python scripts/load-knowledge-base.py --clear
"""

import argparse
import sys
from pathlib import Path

# Add project root to path so we can import src modules
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------

KB_DIR = PROJECT_ROOT / "data" / "knowledge_base"

# Map filenames to domain tags for scoped RAG searches
DOMAIN_MAP = {
    "diabetes_guidelines.md": "endocrinology",
    "hypertension_guidelines.md": "cardiology",
    "drug_interactions.md": "pharmacology",
    "cardiac_workup.md": "cardiology",
    "clinical_trials.md": "clinical-trials",
    "pharmacology_reference.md": "pharmacology",
}

# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Load knowledge base into pgvector")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be loaded without writing to the database",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Delete all existing chunks before loading",
    )
    args = parser.parse_args()

    # Lazy import so --help works without a live database
    from src.config import get_db_connection
    from src.rag import _ensure_table, chunk_document, create_embedding

    if not KB_DIR.is_dir():
        print(f"Error: Knowledge base directory not found: {KB_DIR}")
        sys.exit(1)

    md_files = sorted(KB_DIR.glob("*.md"))
    if not md_files:
        print(f"Error: No .md files found in {KB_DIR}")
        sys.exit(1)

    print(f"Knowledge base: {KB_DIR}")
    print(f"Files found:    {len(md_files)}")
    print()

    if args.dry_run:
        total_chunks = 0
        for f in md_files:
            content = f.read_text(encoding="utf-8")
            chunks = chunk_document(content)
            domain = DOMAIN_MAP.get(f.name, "general")
            print(f"  {f.name:<35} {len(chunks):>3} chunks  [{domain}]")
            total_chunks += len(chunks)
        print(f"\n  Total: {total_chunks} chunks (dry run - nothing written)")
        return

    # Connect
    conn = get_db_connection()
    _ensure_table()

    # Optionally clear existing data
    if args.clear:
        conn.execute("DELETE FROM document_chunks")
        print("Cleared existing chunks from document_chunks")
        print()

    # Check for already-loaded documents
    existing = set()
    rows = conn.execute("SELECT DISTINCT source FROM document_chunks").fetchall()
    for row in rows:
        existing.add(row[0])

    total_chunks = 0
    skipped = 0

    for f in md_files:
        source = f.name
        domain = DOMAIN_MAP.get(source, "general")

        if source in existing and not args.clear:
            print(f"  SKIP  {source:<35} (already loaded)")
            skipped += 1
            continue

        content = f.read_text(encoding="utf-8")
        chunks = chunk_document(content)

        print(f"  LOAD  {source:<35} {len(chunks):>3} chunks  [{domain}]", end="", flush=True)

        for i, chunk in enumerate(chunks):
            embedding = create_embedding(chunk)
            conn.execute(
                """
                INSERT INTO document_chunks (source, content, metadata, domain, embedding)
                VALUES (%s, %s, %s::jsonb, %s, %s::vector)
                """,
                (
                    source,
                    chunk,
                    f'{{"file": "{source}", "chunk_index": {i}}}',
                    domain,
                    str(embedding),
                ),
            )

        total_chunks += len(chunks)
        print("  OK")

    print()
    print(f"Loaded:  {total_chunks} chunks from {len(md_files) - skipped} files")
    if skipped:
        print(f"Skipped: {skipped} files (already in database, use --clear to reload)")

    # Verify
    count = conn.execute("SELECT COUNT(*) FROM document_chunks").fetchone()[0]
    print(f"Total chunks in database: {count}")


if __name__ == "__main__":
    main()
