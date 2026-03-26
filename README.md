# Scaleway Medical AI Lab

Workshop materials for a **[Scaleway](https://www.scaleway.com/) x [cloudaura.io](https://cloudaura.io/)** hands-on session on building healthcare AI applications. The lab demonstrates how to use Scaleway's sovereign European cloud infrastructure and [Mistral AI](https://mistral.ai/) models to solve real medical use cases: speech transcription, document understanding, and multi-domain research agents. All patient data stays in Europe, on infrastructure you control.

## What's in this repo

Three self-contained showcase applications, each demonstrating a different Scaleway AI capability applied to healthcare:

| # | Showcase | What it does | Scaleway services | Mistral models |
|---|----------|-------------|-------------------|----------------|
| 1 | **Ambient Scribe** | Transcribes a doctor-patient conversation and extracts structured clinical data | Generative APIs | Voxtral (STT), Mistral Small 3.2 (extraction) |
| 2 | **Document Intelligence** | OCR on scanned medical documents, indexes them, answers questions with citations | Generative APIs, Managed Inference, PostgreSQL + pgvector, Object Storage | Pixtral (vision/OCR), BGE (embeddings) |
| 3 | **Research Agent** | Searches across pharmacology, cardiology, and clinical trial databases to answer complex medical questions | Generative APIs, Managed Inference, PostgreSQL + pgvector | Mistral Small 3.2 (agent + tool calling), BGE (embeddings) |

A Scaleway account with API keys is required to run the showcases. Scaleway offers a free trial with credits to get started.

## Repo structure

```
.
├── infrastructure/          OpenTofu to provision Scaleway resources
│   ├── main.tf              PostgreSQL + pgvector, Object Storage, Managed Inference
│   ├── variables.tf
│   ├── outputs.tf
│   └── init-db.sql          Database schema (vector extension, tables, indexes)
│
├── src/                     Shared Python modules used by all showcases
│   ├── config.py            API clients (Generative APIs, Managed Inference, PostgreSQL, S3)
│   ├── models.py            JSON schemas for Mistral structured output
│   ├── rag.py               RAG pipeline (chunk, embed, store in pgvector, search, cite)
│   ├── transcription.py     Voxtral speech-to-text
│   ├── extraction.py        Structured clinical data extraction
│   ├── ocr.py               Pixtral document OCR
│   ├── agent.py             Tool-calling agent loop
│   ├── verification.py      Chain-of-Verification (fact-checks claims against sources)
│   └── guardrails.py        Medical disclaimers, audit logging, citation enforcement
│
├── 01_ambient_scribe/       Showcase 1: FastAPI + vanilla HTML/CSS/JS
├── 02_document_intelligence/ Showcase 2
├── 03_research_agent/        Showcase 3
│
├── data/
│   ├── knowledge_base/      Medical guidelines, drug interactions, clinical trials (synthetic)
│   ├── clinical_notes/      Sample doctor-patient notes
│   ├── audio/               Audio recordings (add your own .wav/.mp3)
│   └── documents/           Medical PDFs (add your own)
│
├── requirements.txt
├── .env.example
└── PLAN.md                  Full implementation plan and architecture details
```

## Quick start

### 1. Set up Scaleway infrastructure

```bash
# Provision resources (PostgreSQL + pgvector, Object Storage, Managed Inference)
cp infrastructure/terraform.tfvars.example infrastructure/terraform.tfvars
# Edit terraform.tfvars with your Scaleway credentials
cd infrastructure && tofu init && tofu apply
```

### 2. Configure environment

```bash
cp .env.example .env
# Fill in API keys and connection strings from tofu output

# Initialize database schema
psql "$DATABASE_URL" -f infrastructure/init-db.sql
```

### 3. Run a showcase

```bash
pip install -r requirements.txt

cd 01_ambient_scribe   # or 02_document_intelligence, 03_research_agent
uvicorn main:app --reload --port 8001
# Open http://localhost:8001
```

## Scaleway services used

| Service | Purpose | Why |
|---------|---------|-----|
| **Generative APIs** | Chat, STT, vision, structured output | Serverless, OpenAI-compatible, pay-per-token |
| **Managed Inference** | Dedicated embedding model (BGE) on L4 GPU | Patient data never leaves your dedicated instance |
| **Managed PostgreSQL** | Vector store (pgvector) for RAG | Managed, European-hosted, supports vector search |
| **Object Storage** | Medical documents and audio files | S3-compatible, GDPR-compliant storage |

## Models

| Model | Parameters | Use |
|-------|-----------|-----|
| `mistral-small-3.2` | 24B (dense) | Chat, extraction, agent, tool calling |
| `voxtral-small` | 24.3B | Speech-to-text |
| `pixtral-12b` | 12.4B | Document OCR and vision |
| `bge-multilingual-gemma2` | ~9B | Text embeddings for RAG |

## Medical AI safety

All showcases implement layered trustworthiness patterns relevant to regulated healthcare environments:

- **Grounded RAG with citations**:every medical claim references a source document
- **Structured output validation**:Mistral's native JSON schema mode guarantees valid data
- **Human-in-the-loop**:AI outputs are suggestions, not decisions
- **Chain-of-Verification**:claims are independently fact-checked against the knowledge base
- **Audit logging**:all queries, responses, and sources are recorded

These are architectural patterns, not compliance certifications. See `PLAN.md` for the full safety architecture.

## Prerequisites

- Python 3.11+
- OpenTofu 1.5+ (for infrastructure provisioning)
- A [Scaleway account](https://www.scaleway.com/) with API keys (free trial available)

## License

Workshop materials for educational use.
