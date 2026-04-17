"""
Retrieval-Augmented Generation (RAG) pipeline.

- Embedding via BGE on a dedicated Managed Inference endpoint
- Chunking with configurable size / overlap
- Indexing and similarity search against pgvector
- Response generation with mandatory citations
"""

from __future__ import annotations

import json
import logging
import uuid

from src.config import (
    CHAT_MODEL,
    EMBEDDING_DIMENSIONS,
    EMBEDDING_MODEL,
    get_db_connection,
    get_generative_client,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Embedding
# ---------------------------------------------------------------------------


def create_embedding(text: str) -> list[float]:
    """Create a dense vector for *text* via Scaleway Generative APIs.

    Uses the same Qwen3 embedding model + dimension count as the Drug
    Interactions showcase so the dimension across showcases stays
    consistent.
    """
    logger.info("create_embedding called, text_length=%d chars", len(text))
    client = get_generative_client()
    logger.debug("Requesting embedding from model=%s dim=%d", EMBEDDING_MODEL, EMBEDDING_DIMENSIONS)
    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=text,
        dimensions=EMBEDDING_DIMENSIONS,
    )
    embedding = response.data[0].embedding
    logger.info("create_embedding completed, dimensions=%d", len(embedding))
    return embedding


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------


# Reject chunks shorter than this. OCR of medical PDFs produces many
# tiny artifacts (page numbers like "1", footer lines, lone table cells)
# that get embedded as near-random vectors and pollute top-k retrieval.
MIN_CHUNK_LEN = 50


def chunk_document(
    text: str,
    chunk_size: int = 500,
    overlap: int = 100,
) -> list[str]:
    """Split *text* into overlapping chunks of roughly *chunk_size* characters.

    Uses a simple character-level sliding window.  Splits are attempted at
    the nearest newline or sentence boundary inside the window to avoid
    cutting mid-word. Chunks shorter than ``MIN_CHUNK_LEN`` are dropped
    so noise (page numbers, lone table cells) never reaches the index.
    """
    logger.info(
        "chunk_document called, text_length=%d, chunk_size=%d, overlap=%d",
        len(text) if text else 0,
        chunk_size,
        overlap,
    )
    if not text:
        logger.warning("chunk_document received empty text, returning empty list")
        return []

    raw_chunks: list[str] = []
    start = 0
    length = len(text)

    while start < length:
        end = min(start + chunk_size, length)

        if end < length:
            for sep in ("\n\n", "\n", ". "):
                boundary = text.rfind(sep, start + overlap, end)
                if boundary != -1:
                    end = boundary + len(sep)
                    break

        chunk = text[start:end].strip()
        if chunk:
            raw_chunks.append(chunk)

        # Always advance by at least chunk_size//2 so we can't loop on a
        # near-window boundary producing micro-chunks of a few characters.
        next_start = max(end - overlap, start + chunk_size // 2)
        if next_start <= start:
            next_start = start + 1
        start = next_start

    chunks = [c for c in raw_chunks if len(c) >= MIN_CHUNK_LEN]
    dropped = len(raw_chunks) - len(chunks)
    if dropped:
        logger.info("chunk_document dropped %d sub-%d-char chunks", dropped, MIN_CHUNK_LEN)
    logger.info("chunk_document completed, produced %d chunks", len(chunks))
    return chunks


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

_TABLE_INIT_SQL = f"""
CREATE TABLE IF NOT EXISTS document_chunks (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source      TEXT NOT NULL,
    content     TEXT NOT NULL,
    metadata    JSONB DEFAULT '{{}}',
    domain      TEXT,
    embedding   vector({EMBEDDING_DIMENSIONS}),
    created_at  TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_chunks_domain
    ON document_chunks (domain);
"""


def _ensure_table() -> None:
    logger.debug("Ensuring document_chunks table exists")
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
    logger.info("index_document called, source=%s, content_length=%d, domain=%s", source, len(content), domain)
    _ensure_table()
    conn = get_db_connection()
    chunks = chunk_document(content)
    meta_json = json.dumps(metadata or {})
    logger.debug("Indexing %d chunks for source=%s", len(chunks), source)

    for i, chunk in enumerate(chunks):
        logger.debug("Embedding chunk %d/%d (length=%d)", i + 1, len(chunks), len(chunk))
        embedding = create_embedding(chunk)
        conn.execute(
            """
            INSERT INTO document_chunks (id, source, content, metadata, domain, embedding)
            VALUES (%s, %s, %s, %s::jsonb, %s, %s::vector)
            """,
            (str(uuid.uuid4()), source, chunk, meta_json, domain, str(embedding)),
        )

    logger.info("index_document completed, chunks_indexed=%d, source=%s", len(chunks), source)
    return len(chunks)


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


def search(
    query: str,
    top_k: int = 10,
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
    logger.info("search called, query=%r, top_k=%d, domain=%s", query[:80], top_k, domain)
    _ensure_table()
    conn = get_db_connection()
    embedding = create_embedding(query)
    logger.debug("Query embedding created, dimensions=%d", len(embedding))

    if domain:
        logger.debug("Executing domain-filtered similarity search, domain=%s", domain)
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
        logger.debug("Executing unfiltered similarity search")
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

    results = [
        {
            "id": str(row[0]),
            "source": row[1],
            "content": row[2],
            "metadata": row[3],
            "score": float(row[4]),
        }
        for row in rows
    ]

    if not results:
        logger.warning("search returned 0 results for query=%r, domain=%s", query[:80], domain)
    else:
        logger.info("search completed, results=%d, top_score=%.4f", len(results), results[0]["score"])

    return results


# ---------------------------------------------------------------------------
# Cited response generation
# ---------------------------------------------------------------------------

_RAG_SYSTEM_PROMPT = """\
You are a medical knowledge assistant. Answer the user's question using
the provided context chunks.

Be helpful and direct:
- If the context contains the answer (even under a synonym, abbreviation,
  or different phrasing), give the answer. Examples: user asks "gender?"
  and the context says "Sex: Male" -> answer "Male". User asks
  "Lymphocytes?" and the context shows "Lymphocytes 30 %" in a lab
  table -> answer "30%".
- Single-word or terse questions are valid; treat them as a request for
  the corresponding fact in the context.
- Every factual statement MUST include a citation in the format
  [Source: <source>].
- Use precise medical terminology and structure long answers with clear
  paragraphs.
- ONLY say the context lacks the information when, after careful reading,
  no chunk contains a relevant fact. This should be the last resort, not
  the default response.
- Do NOT invent facts or references that are not supported by the context.
"""

_QUERY_REWRITE_PROMPT = """\
You rewrite short user questions into rich retrieval queries for a
vector search over medical documents (lab reports, discharge summaries,
imaging reports, clinical notes).

Goal: produce a query string whose embedding will land near the right
section of the document, even when the user's input is one or two
words. Short queries embed too thinly; pad them with the medical
phrasings that the actual document is likely to contain.

Rules:
- Output ONLY the rewritten query string. No explanation, no quotes,
  no prefix like "Query:".
- Aim for 15-30 words. Verbose is good; recall matters more than
  precision at this stage.
- Include 2-4 synonyms or closely related medical terms.
- Include the section/category headings the answer would appear under
  (e.g. for "gender?" think "patient information demographics"; for
  "Lymphocytes?" think "complete blood count differential").
- Preserve the user's intent. Don't add facts.
- If the input is already a full sentence or longer than 8 words,
  return it unchanged.

Examples:
  "gender?"
    -> patient information demographics gender or biological sex male female age date of birth
  "Lymphocytes?"
    -> complete blood count CBC differential lymphocyte count percentage value reference range
  "HbA1c?"
    -> hemoglobin A1c HbA1c glycated hemoglobin diabetes glycemic control lab result value
  "abnormal lab values"
    -> flagged abnormal lab results high low values out of reference range clinical findings
  "any allergies"
    -> patient allergies allergic reactions known sensitivities medication intolerance
"""


def _rewrite_query(query: str) -> str:
    """Expand a short user query into a richer retrieval query.

    Returns the rewritten string, or the original query on any failure
    (so retrieval still happens, just without the recall boost).
    """
    if not query or not query.strip():
        return query
    try:
        client = get_generative_client()
        response = client.chat.completions.create(
            model=CHAT_MODEL,
            messages=[
                {"role": "system", "content": _QUERY_REWRITE_PROMPT},
                {"role": "user", "content": query.strip()},
            ],
            temperature=0.0,
            max_tokens=80,
        )
        rewritten = (response.choices[0].message.content or "").strip()
        # Strip enclosing quotes the model sometimes adds despite the rule.
        if len(rewritten) >= 2 and rewritten[0] in ('"', "'") and rewritten[-1] == rewritten[0]:
            rewritten = rewritten[1:-1].strip()
        if not rewritten:
            return query
        return rewritten
    except Exception as exc:
        logger.warning("Query rewrite failed (%s); using original query", exc)
        return query


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
        Results from :func:`search` - each must have ``source`` and ``content``.

    Returns
    -------
    str
        The generated answer with [Source: ...] citations.
    """
    logger.info("generate_cited_response called, query=%r, context_chunks=%d", query[:80], len(context_chunks))
    context_parts: list[str] = []
    for i, chunk in enumerate(context_chunks, 1):
        context_parts.append(f"[{i}] Source: {chunk['source']}\n{chunk['content']}")
    context_block = "\n\n---\n\n".join(context_parts)

    user_message = f"Context:\n{context_block}\n\n---\n\nQuestion: {query}"

    client = get_generative_client()
    logger.debug("Sending cited-response request to model=%s, context_length=%d chars", CHAT_MODEL, len(context_block))
    response = client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[
            {"role": "system", "content": _RAG_SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        temperature=0.2,
    )

    content = response.choices[0].message.content
    logger.info("generate_cited_response completed, response_length=%d chars", len(content) if content else 0)
    return content
