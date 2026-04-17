# Showcase 2 — Medical Document Intelligence

Vision-to-RAG pipeline for scanned medical documents. Upload PDFs, extract text via Mistral Small 3.2 vision, embed and index into pgvector, then query with natural-language questions that return cited answers.

![Document Intelligence UI](../docs/document_example.png)

## What it does

1. **Upload** a PDF (e.g. a scanned discharge summary or lab report).
2. **Vision extraction** — each page is sent to Mistral Small 3.2's native vision mode on Scaleway Generative APIs (Pixtral is deprecated; Mistral Small 3.2 reads document text and layout directly).
3. **Chunk + embed** — text is split (500 chars, 100 overlap), embedded via **Qwen3 Embedding 8B** on Scaleway Managed Inference (L4 GPU), and written to a PostgreSQL + pgvector store.
4. **Query** — natural-language questions trigger a similarity search, a query rewrite pass, and a Mistral Small 3.2 answer with inline citations.

## Models & services

| Stage | Scaleway Service | Model | Size |
|---|---|---|---|
| Vision extraction | Generative APIs (serverless) | `mistral-small-3.2-24b-instruct-2506` | 24B |
| Embeddings | Managed Inference (dedicated L4 GPU) | `qwen3-embedding-8b` | 8B, 768-dim |
| Vector store | Managed PostgreSQL (DB-DEV-S) | `pgvector` | — |
| Answer generation | Generative APIs (serverless) | `mistral-small-3.2-24b-instruct-2506` | 24B |
| PDF storage | Object Storage (S3) | — | — |

## Prerequisites

- Scaleway API key with access to Generative APIs and Managed Inference
- PostgreSQL with the `pgvector` extension enabled (provisioned by the repo's terraform)
- Environment variables (see `src/config.py`)

## Quick start

```bash
# From the repo root
cd 02_document_intelligence
pip install -r ../requirements.txt
uvicorn main:app --reload --port 8002
# Open http://localhost:8002
```

## Endpoints

- `GET /` — frontend
- `POST /api/upload` — upload a PDF
- `POST /api/process/{doc_id}` — vision extraction + index (SSE progress stream)
- `POST /api/query` — RAG query with citations
- `GET /api/documents` — list processed documents
- `GET /api/health` — health check
