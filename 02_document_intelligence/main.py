"""
Showcase 2 — Medical Document Intelligence

FastAPI backend that orchestrates:
  1. PDF upload
  2. OCR via Mistral Small 3.2 vision (page-by-page with SSE progress)
  3. Chunking + embedding into pgvector via RAG pipeline
  4. Natural-language queries with cited responses

Requires Scaleway API keys and a PostgreSQL database with pgvector.
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
import uuid
from pathlib import Path

from fastapi import File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Project path setup
# ---------------------------------------------------------------------------
from src.app_factory import setup_project_path

setup_project_path(__file__)

from src.app_factory import (  # noqa: E402
    create_app,
    mount_static,
    create_index_route,
    create_health_endpoint,
)

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
STATIC_DIR = Path(__file__).resolve().parent / "static"

app = create_app(title="Medical Document Intelligence", version="0.1.0")
mount_static(app, STATIC_DIR)
create_index_route(app, STATIC_DIR)

# In-memory state
_UPLOAD_DIR = Path(tempfile.mkdtemp(prefix="medocr_"))

# doc_id -> {filename, path, pages: [{page, text}], chunks_indexed}
_documents: dict[str, dict] = {}

create_health_endpoint(
    app,
    service="document-intelligence",
    documents_loaded=lambda: len(_documents),
)

# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class QueryRequest(BaseModel):
    """Request body for document queries."""

    query: str
    top_k: int = 5


class UploadResponse(BaseModel):
    """Response body for document uploads."""

    doc_id: str
    filename: str


class QueryResponse(BaseModel):
    """Response body for document queries."""

    answer: str
    sources: list[dict]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.post("/api/upload", response_model=UploadResponse)
async def upload_document(file: UploadFile = File(...)):
    """Accept a PDF upload and store it locally."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400, detail="Only PDF files are accepted."
        )

    doc_id = str(uuid.uuid4())
    save_path = _UPLOAD_DIR / f"{doc_id}.pdf"

    content = await file.read()
    save_path.write_bytes(content)

    _documents[doc_id] = {
        "filename": file.filename,
        "path": str(save_path),
        "pages": [],
        "chunks_indexed": 0,
    }

    return UploadResponse(doc_id=doc_id, filename=file.filename)


@app.post("/api/process/{doc_id}")
async def process_document(doc_id: str):
    """Run vision OCR on each page and index via RAG.  Returns SSE stream."""
    if doc_id not in _documents:
        raise HTTPException(status_code=404, detail="Document not found.")

    doc = _documents[doc_id]

    async def event_stream():
        try:
            from src.ocr import process_pdf
            from src.rag import index_document

            yield _sse(
                {"event": "processing_started", "filename": doc["filename"]}
            )

            pages = process_pdf(doc["path"])
            doc["pages"] = pages

            for i, page in enumerate(pages):
                yield _sse({
                    "event": "page_processed",
                    "page": page["page"],
                    "total": len(pages),
                    "text": page["text"],
                })
                await asyncio.sleep(0.1)  # Small pause for UI animation

            # Index the full text
            yield _sse({"event": "indexing_started"})
            full_text = "\n\n".join(p["text"] for p in pages)
            num_chunks = index_document(
                source=doc["filename"],
                content=full_text,
                metadata={"doc_id": doc_id},
            )
            doc["chunks_indexed"] = num_chunks

            yield _sse({
                "event": "indexing_complete",
                "chunks": num_chunks,
            })

            yield _sse({
                "event": "complete",
                "filename": doc["filename"],
                "pages": len(pages),
                "chunks": num_chunks,
            })

        except Exception as exc:
            yield _sse({"event": "error", "detail": str(exc)})

    return StreamingResponse(
        event_stream(), media_type="text/event-stream"
    )


@app.post("/api/query", response_model=QueryResponse)
async def query_documents(req: QueryRequest):
    """Answer a question using RAG over indexed documents."""
    try:
        from src.rag import search, generate_cited_response

        results = search(req.query, top_k=req.top_k)
        if not results:
            return QueryResponse(
                answer=(
                    "No relevant documents found. "
                    "Please upload and process documents first."
                ),
                sources=[],
            )

        answer = generate_cited_response(req.query, results)
        return QueryResponse(
            answer=answer,
            sources=[
                {
                    "source": r["source"],
                    "content": r["content"][:300],
                    "score": r["score"],
                }
                for r in results
            ],
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/documents")
async def list_documents():
    """List all documents that have been uploaded/processed."""
    docs = []

    for doc_id, doc in _documents.items():
        docs.append({
            "doc_id": doc_id,
            "filename": doc["filename"],
            "pages": len(doc["pages"]),
            "chunks_indexed": doc.get("chunks_indexed", 0),
        })

    return {"documents": docs}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sse(data: dict) -> str:
    """Format a dict as an SSE data line."""
    return f"data: {json.dumps(data)}\n\n"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8001")),
        reload=True,
    )
