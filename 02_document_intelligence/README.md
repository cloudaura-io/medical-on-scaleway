# Showcase 2: Medical Document Intelligence

OCR-to-RAG pipeline for scanned medical documents. Upload PDFs, extract text via Pixtral vision, embed and index into pgvector, then query with natural-language questions that return cited answers.

## Prerequisites

- Scaleway API key with access to Generative APIs and Managed Inference
- PostgreSQL database with the pgvector extension enabled
- Environment variables configured (see `src/config.py` for details)

## Quick Start

```bash
# From this directory
pip install fastapi uvicorn python-multipart pdf2image
python main.py
# Open http://localhost:8001
```

## Architecture

| Stage | Scaleway Service | Model |
|---|---|---|
| Document OCR | Generative APIs | `pixtral-12b-2409` |
| Embeddings | Managed Inference (L4 GPU) | `bge-multilingual-gemma2` |
| Vector store | Managed PostgreSQL | pgvector |
| Response generation | Generative APIs | `mistral-small-3.2-24b-instruct-2506` |

## Endpoints

- `GET /` — Frontend
- `POST /api/upload` — Upload a PDF
- `POST /api/process/{doc_id}` — OCR + index (SSE progress stream)
- `POST /api/query` — RAG query with citations
- `GET /api/documents` — List processed documents
- `GET /api/health` — Health check
