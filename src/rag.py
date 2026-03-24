"""
Retrieval-Augmented Generation (RAG) pipeline.

- Embedding via BGE on a dedicated Managed Inference endpoint
- Chunking with configurable size / overlap
- Indexing and similarity search against pgvector
- Response generation with mandatory citations
"""

from __future__ import annotations

import json
import uuid
from typing import Optional

from src.config import (
    get_inference_client,
    get_generative_client,
    get_db_connection,
    EMBEDDING_MODEL,
    CHAT_MODEL,
)

# ---------------------------------------------------------------------------
# Embedding
# ---------------------------------------------------------------------------

def create_embedding(text: str) -> list[float]:
    """Create a dense vector for *text* using the BGE model on Managed Inference.

    The Managed Inference endpoint runs on a dedicated GPU so patient data
    never traverses shared infrastructure.
    """
    client = get_inference_client()
    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=text,
    )
    return response.data[0].embedding


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def chunk_document(
    text: str,
    chunk_size: int = 500,
    overlap: int = 100,
) -> list[str]:
    """Split *text* into overlapping chunks of roughly *chunk_size* characters.

    Uses a simple character-level sliding window.  Splits are attempted at
    the nearest newline or sentence boundary inside the window to avoid
    cutting mid-word.
    """
    if not text:
        return []

    chunks: list[str] = []
    start = 0
    length = len(text)

    while start < length:
        end = min(start + chunk_size, length)

        # Try to break at a paragraph or sentence boundary.
        if end < length:
            # Prefer double-newline, then single newline, then period+space.
            for sep in ("\n\n", "\n", ". "):
                boundary = text.rfind(sep, start + overlap, end)
                if boundary != -1:
                    end = boundary + len(sep)
                    break

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        # Advance by (end - overlap), but at least 1 char to avoid infinite loop.
        start = max(end - overlap, start + 1)

    return chunks


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

_TABLE_INIT_SQL = """
CREATE TABLE IF NOT EXISTS document_chunks (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source      TEXT NOT NULL,
    content     TEXT NOT NULL,
    metadata    JSONB DEFAULT '{}',
    domain      TEXT,
    embedding   vector(768),
    created_at  TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_chunks_embedding
    ON document_chunks USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
CREATE INDEX IF NOT EXISTS idx_chunks_domain
    ON document_chunks (domain);
"""


def _ensure_table() -> None:
    conn = get_db_connection()
    conn.execute(_TABLE_INIT_SQL)


# ---------------------------------------------------------------------------
# Indexing
# ---------------------------------------------------------------------------

def index_document(
    source: str,
    content: str,
    metadata: dict | None = None,
    domain: str | None = None,
) -> int:
    """Chunk, embed, and store a document in pgvector.

    Parameters
    ----------
    source:
        Human-readable identifier (filename, URL, etc.).
    content:
        Full text of the document.
    metadata:
        Arbitrary JSON metadata stored alongside each chunk.
    domain:
        Optional domain tag for scoped searches (e.g., "pharmacology").

    Returns
    -------
    int
        Number of chunks indexed.
    """
    _ensure_table()
    conn = get_db_connection()
    chunks = chunk_document(content)
    meta_json = json.dumps(metadata or {})

    for chunk in chunks:
        embedding = create_embedding(chunk)
        conn.execute(
            """
            INSERT INTO document_chunks (id, source, content, metadata, domain, embedding)
            VALUES (%s, %s, %s, %s::jsonb, %s, %s::vector)
            """,
            (str(uuid.uuid4()), source, chunk, meta_json, domain, str(embedding)),
        )

    return len(chunks)


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

def search(
    query: str,
    top_k: int = 5,
    domain: str | None = None,
) -> list[dict]:
    """Embed *query* and retrieve the most similar chunks.

    Parameters
    ----------
    query:
        Natural-language query.
    top_k:
        Maximum number of results.
    domain:
        If provided, restrict to chunks with this domain tag.

    Returns
    -------
    list[dict]
        Each dict contains: id, source, content, metadata, score.
    """
    _ensure_table()
    conn = get_db_connection()
    embedding = create_embedding(query)

    if domain:
        rows = conn.execute(
            """
            SELECT id, source, content, metadata,
                   1 - (embedding <=> %s::vector) AS score
            FROM   document_chunks
            WHERE  domain = %s
            ORDER  BY embedding <=> %s::vector
            LIMIT  %s
            """,
            (str(embedding), domain, str(embedding), top_k),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT id, source, content, metadata,
                   1 - (embedding <=> %s::vector) AS score
            FROM   document_chunks
            ORDER  BY embedding <=> %s::vector
            LIMIT  %s
            """,
            (str(embedding), str(embedding), top_k),
        ).fetchall()

    return [
        {
            "id": str(row[0]),
            "source": row[1],
            "content": row[2],
            "metadata": row[3],
            "score": float(row[4]),
        }
        for row in rows
    ]


# ---------------------------------------------------------------------------
# Cited response generation
# ---------------------------------------------------------------------------

_RAG_SYSTEM_PROMPT = """\
You are a medical knowledge assistant.  Answer the user's question using
ONLY the provided context chunks.

Rules:
- Every factual statement MUST include a citation in the format [Source: <source>].
- If the context does not contain enough information, say so explicitly.
- Do NOT invent facts or references.
- Use precise medical terminology.
- Structure your response with clear paragraphs.
"""


def generate_cited_response(
    query: str,
    context_chunks: list[dict],
) -> str:
    """Generate a response grounded in retrieved context with inline citations.

    Parameters
    ----------
    query:
        The user's question.
    context_chunks:
        Results from :func:`search` — each must have ``source`` and ``content``.

    Returns
    -------
    str
        The generated answer with [Source: ...] citations.
    """
    # Build a numbered context block so the model can reference sources.
    context_parts: list[str] = []
    for i, chunk in enumerate(context_chunks, 1):
        context_parts.append(
            f"[{i}] Source: {chunk['source']}\n{chunk['content']}"
        )
    context_block = "\n\n---\n\n".join(context_parts)

    user_message = (
        f"Context:\n{context_block}\n\n---\n\nQuestion: {query}"
    )

    client = get_generative_client()
    response = client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[
            {"role": "system", "content": _RAG_SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        temperature=0.2,
    )

    return response.choices[0].message.content
