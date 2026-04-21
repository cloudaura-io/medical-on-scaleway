"""pgvector helpers for the drug interaction RAG pipeline.

Provides table creation, bulk insert, and similarity search operations
against a PostgreSQL database with pgvector extension for storing and
querying section-typed FDA drug label chunks.

Adapted from workshop/src/rag.py for the Drug Interactions showcase.
Uses a dedicated ``drug_chunks`` table (separate from the
``document_chunks`` table used by Showcase 2).
"""

from __future__ import annotations

import logging
from typing import Any

from psycopg.rows import dict_row

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Table creation
# ---------------------------------------------------------------------------

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS drug_chunks (
    id SERIAL PRIMARY KEY,
    drug_name TEXT NOT NULL,
    generic_name TEXT NOT NULL,
    brand_name TEXT NOT NULL,
    section_type TEXT NOT NULL,
    set_id TEXT NOT NULL,
    application_number TEXT,
    manufacturer_name TEXT,
    label_url TEXT NOT NULL,
    text TEXT NOT NULL,
    embedding vector(768)
);
"""

CREATE_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_drug_chunks_embedding
    ON drug_chunks USING hnsw (embedding vector_cosine_ops);
"""


def create_drug_table(conn: Any) -> None:
    """Create the drug_chunks table and HNSW vector index if they do not exist.

    Args:
        conn: A psycopg connection object.
    """
    with conn.cursor() as cur:
        cur.execute(CREATE_TABLE_SQL)
        cur.execute(CREATE_INDEX_SQL)
    conn.commit()
    logger.info("drug_chunks table and HNSW index ensured")


# ---------------------------------------------------------------------------
# Insert
# ---------------------------------------------------------------------------

INSERT_SQL = """
INSERT INTO drug_chunks (
    drug_name, generic_name, brand_name, section_type, set_id,
    application_number, manufacturer_name, label_url, text, embedding
) VALUES (
    %(drug_name)s, %(generic_name)s, %(brand_name)s, %(section_type)s,
    %(set_id)s, %(application_number)s, %(manufacturer_name)s,
    %(label_url)s, %(text)s, %(embedding)s
)
"""


def insert_drug_chunks(conn: Any, chunks: list[dict[str, Any]]) -> None:
    """Bulk-insert chunks into the pgvector drug_chunks table.

    Args:
        conn: A psycopg connection object.
        chunks: List of chunk dicts with all required fields including
            'embedding' (list of floats).
    """
    with conn.cursor() as cur:
        for chunk in chunks:
            params = {
                "drug_name": chunk["drug_name"],
                "generic_name": chunk["generic_name"],
                "brand_name": chunk["brand_name"],
                "section_type": chunk["section_type"],
                "set_id": chunk["set_id"],
                "application_number": chunk.get("application_number", ""),
                "manufacturer_name": chunk.get("manufacturer_name", ""),
                "label_url": chunk["label_url"],
                "text": chunk["text"],
                "embedding": chunk.get("embedding"),
            }
            cur.execute(INSERT_SQL, params)
    conn.commit()
    logger.info("Inserted %d drug chunks", len(chunks))


# ---------------------------------------------------------------------------
# Similarity search
# ---------------------------------------------------------------------------


def drug_similarity_search(
    conn: Any,
    query_embedding: list[float],
    k: int = 5,
    filters: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Search for the most similar drug chunks using cosine distance.

    Args:
        conn: A psycopg connection object.
        query_embedding: The query embedding vector.
        k: Number of results to return.
        filters: Optional dict of column filters. Supported keys:
            'drug_name', 'section_type'.

    Returns:
        List of result dicts with chunk fields and distance score.
    """
    where_clauses: list[str] = []
    params: dict[str, Any] = {
        "query_embedding": query_embedding,
        "k": k,
    }

    if filters:
        if "drug_name" in filters:
            where_clauses.append("LOWER(drug_name) LIKE LOWER(%(filter_drug_name)s)")
            params["filter_drug_name"] = f"%{filters['drug_name']}%"
        if "section_type" in filters:
            where_clauses.append("section_type = %(filter_section_type)s")
            params["filter_section_type"] = filters["section_type"]

    where_sql = ""
    if where_clauses:
        where_sql = "WHERE " + " AND ".join(where_clauses)

    sql = f"""
        SELECT drug_name, generic_name, brand_name, section_type, set_id,
               application_number, manufacturer_name, label_url, text,
               embedding <=> %(query_embedding)s::vector AS distance
        FROM drug_chunks
        {where_sql}
        ORDER BY embedding <=> %(query_embedding)s::vector
        LIMIT %(k)s
    """

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()

    return rows
