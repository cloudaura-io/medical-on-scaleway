"""pgvector helpers for the workshop RAG pipeline.

Provides insert and similarity search operations against a PostgreSQL
database with pgvector extension for storing and querying section-typed
drug label chunks.
"""

from __future__ import annotations

import logging
from typing import Any

from pgvector.psycopg import register_vector
from psycopg.rows import dict_row

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Table creation
# ---------------------------------------------------------------------------

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS chunks (
    id SERIAL PRIMARY KEY,
    drug_name TEXT NOT NULL,
    generic_name TEXT NOT NULL,
    brand_name TEXT NOT NULL,
    section_type TEXT NOT NULL,
    set_id TEXT NOT NULL,
    application_number TEXT,
    manufacturer_name TEXT,
    source_url TEXT,
    text TEXT NOT NULL,
    embedding vector(3584)
);
"""

CREATE_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_chunks_embedding
    ON chunks USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 20);
"""


def create_table(conn: Any) -> None:
    """Create the chunks table and vector index if they do not exist.

    Also registers the pgvector type adapter on the connection so that
    `list[float]` parameters bind as pgvector `vector` values.

    Args:
        conn: A psycopg connection object. The `vector` extension must
            already be enabled on the database.
    """
    register_vector(conn)
    with conn.cursor() as cur:
        cur.execute(CREATE_TABLE_SQL)
        cur.execute(CREATE_INDEX_SQL)
    conn.commit()


# ---------------------------------------------------------------------------
# Insert
# ---------------------------------------------------------------------------

INSERT_SQL = """
INSERT INTO chunks (
    drug_name, generic_name, brand_name, section_type, set_id,
    application_number, manufacturer_name, source_url, text, embedding
) VALUES (
    %(drug_name)s, %(generic_name)s, %(brand_name)s, %(section_type)s,
    %(set_id)s, %(application_number)s, %(manufacturer_name)s,
    %(source_url)s, %(text)s, %(embedding)s
)
"""


def insert_chunks(conn: Any, chunks: list[dict[str, Any]]) -> None:
    """Bulk-insert chunks into the pgvector chunks table.

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
                "source_url": chunk.get("source_url", ""),
                "text": chunk["text"],
                "embedding": chunk.get("embedding"),
            }
            cur.execute(INSERT_SQL, params)
    conn.commit()
    logger.info("Inserted %d chunks", len(chunks))


# ---------------------------------------------------------------------------
# Similarity search
# ---------------------------------------------------------------------------


def similarity_search(
    conn: Any,
    query_embedding: list[float],
    k: int = 5,
    filters: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Search for the most similar chunks using cosine distance.

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
               application_number, manufacturer_name, source_url, text,
               embedding <=> %(query_embedding)s::vector AS distance
        FROM chunks
        {where_sql}
        ORDER BY embedding <=> %(query_embedding)s::vector
        LIMIT %(k)s
    """

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()

    return rows
