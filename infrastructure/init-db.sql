--------------------------------------------------------------------------------
-- Scaleway Medical AI Lab - Database Initialization
-- Run against the medical_knowledge database after Terraform provisioning:
--   psql "$DATABASE_URL" -f init-db.sql
--------------------------------------------------------------------------------

-- pgvector extension for embedding storage and similarity search
CREATE EXTENSION IF NOT EXISTS vector;

--------------------------------------------------------------------------------
-- documents: raw medical documents ingested into the knowledge base
--------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS documents (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source     TEXT        NOT NULL,
    content    TEXT        NOT NULL,
    metadata   JSONB       NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE documents IS 'Raw medical documents (PDFs, guidelines, formularies) ingested into the RAG pipeline';

--------------------------------------------------------------------------------
-- embeddings: vector chunks produced from documents
--------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS embeddings (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    doc_id     BIGINT       NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_text TEXT         NOT NULL,
    embedding  vector(768)  NOT NULL,
    metadata   JSONB        NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ  NOT NULL DEFAULT now()
);

COMMENT ON TABLE embeddings IS 'Chunked text with 768-dim embeddings from bge-multilingual-gemma2';

-- HNSW index for fast approximate nearest-neighbour search (cosine distance)
CREATE INDEX IF NOT EXISTS idx_embeddings_vector
    ON embeddings
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- Speed up joins back to the source document
CREATE INDEX IF NOT EXISTS idx_embeddings_doc_id
    ON embeddings (doc_id);

--------------------------------------------------------------------------------
-- audit_log: every RAG query and its response for compliance/traceability
--------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit_log (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    timestamp  TIMESTAMPTZ NOT NULL DEFAULT now(),
    action     TEXT        NOT NULL,
    query      TEXT,
    response   TEXT,
    sources    JSONB,
    metadata   JSONB       NOT NULL DEFAULT '{}'
);

COMMENT ON TABLE audit_log IS 'Immutable audit trail for all RAG queries (medical compliance)';

CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp
    ON audit_log (timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_audit_log_action
    ON audit_log (action);
