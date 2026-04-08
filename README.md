# Scaleway Medical AI Lab

Workshop materials for a **[Scaleway](https://www.scaleway.com/) x [cloudaura.io](https://cloudaura.io/)** hands-on session on building healthcare AI applications. The lab demonstrates how to use Scaleway's sovereign European cloud infrastructure and [Mistral AI](https://mistral.ai/) models to solve real medical use cases: speech transcription, document understanding, and multi-domain research agents. All patient data stays in Europe, on infrastructure you control.

## What's in this repo

Three self-contained showcase applications, each demonstrating a different Scaleway AI capability applied to healthcare:

| # | Showcase | What it does | Scaleway services | Mistral models |
|---|----------|-------------|-------------------|----------------|
| 1 | **Ambient Scribe** | Transcribes doctor-patient conversations (file upload or realtime WebSocket streaming) and extracts structured clinical data | Generative APIs, GPU Instance (L4 + vLLM) | Voxtral (STT), Voxtral Mini 4B Realtime (streaming STT), Mistral Small 3.2 (extraction) |
| 2 | **Document Intelligence** | OCR on scanned medical documents, indexes them, answers questions with citations | Generative APIs, Managed Inference, PostgreSQL + pgvector, Object Storage | Mistral Small 3.2 (vision/OCR), BGE (embeddings) |
| 3 | **Research Agent** | Searches across pharmacology, cardiology, and clinical trial databases to answer complex medical questions | Generative APIs, Managed Inference, PostgreSQL + pgvector | Mistral Small 3.2 (agent + tool calling), BGE (embeddings) |

A Scaleway account with API keys is required to run the showcases. [Register for a free Scaleway account](https://account.scaleway.com/register) to get **€100 in free credits** — enough to run all three showcases.

## Repo structure

```
.
├── infrastructure/              OpenTofu to provision Scaleway resources
│   ├── main.tf                  PostgreSQL + pgvector, Object Storage, Managed Inference, GPU Instance
│   ├── variables.tf
│   ├── outputs.tf
│   ├── init-db.sql              Database schema (vector extension, tables, indexes)
│   └── cloud-init-vllm.yaml    Cloud-init for L4 GPU instance (Docker + vLLM + Voxtral Realtime)
│
├── src/                         Shared Python modules used by all showcases
│   ├── config.py                API clients (Generative APIs, Managed Inference, PostgreSQL, S3)
│   ├── models.py                JSON schemas for Mistral structured output
│   ├── app_factory.py           Shared FastAPI app setup (CORS, static files, health endpoint)
│   ├── rag.py                   RAG pipeline (chunk, embed, store in pgvector, search, cite)
│   ├── transcription.py         Voxtral speech-to-text (file upload)
│   ├── transcription_realtime.py  Voxtral Realtime WebSocket streaming transcription
│   ├── extraction.py            Structured clinical data extraction
│   ├── ocr.py                   Mistral Small 3.2 document OCR (vision)
│   ├── agent.py                 Tool-calling agent loop
│   ├── verification.py          Chain-of-Verification (fact-checks claims against sources)
│   ├── guardrails.py            Medical disclaimers, audit logging, citation enforcement
│   ├── sse_utils.py             Server-sent events formatting utilities
│   └── logging_config.py        Structured logging configuration
│
├── 01_ambient_scribe/           Showcase 1: FastAPI + vanilla HTML/CSS/JS
├── 02_document_intelligence/    Showcase 2
├── 03_research_agent/           Showcase 3
│
├── scripts/                     Setup, teardown, and utility scripts
│   ├── setup.sh                 Full provisioning pipeline (infra + env + DB + knowledge base)
│   ├── teardown.sh              Destroy all Scaleway resources
│   ├── load-knowledge-base.py   Index medical guidelines into pgvector
│   └── validate.py              Test connectivity to all Scaleway services
│
├── tests/                       Test suite (pytest)
│
├── data/
│   ├── knowledge_base/          Medical guidelines, drug interactions, clinical trials (synthetic)
│   ├── sample_audio/            Sample doctor-patient consultation audio
│   ├── clinical_notes/          Sample clinical notes
│   ├── audio/                   Audio recordings (add your own .wav/.mp3)
│   └── documents/               Medical PDFs (add your own)
│
├── static/shared/               Shared CSS/JS utilities for all frontends
├── requirements.txt
├── .env.example
└── PLAN.md                      Full implementation plan and architecture details
```

## Quick start

### Option A: Automated setup

```bash
bash scripts/setup.sh          # provisions infra, generates .env, inits DB, loads knowledge base
# bash scripts/setup.sh --skip-tofu   # skip infrastructure if already provisioned
```

### Option B: Manual setup

#### 1. Set up Scaleway infrastructure

```bash
# Provision resources (PostgreSQL + pgvector, Object Storage, Managed Inference, GPU Instance)
cp infrastructure/terraform.tfvars.example infrastructure/terraform.tfvars
# Edit terraform.tfvars with your Scaleway credentials
cd infrastructure && tofu init && tofu apply
```

#### 2. Configure environment

```bash
cp .env.example .env
# Fill in API keys and connection strings from tofu output

# Initialize database schema
psql "$DATABASE_URL" -f infrastructure/init-db.sql

# Load medical knowledge base into pgvector
python scripts/load-knowledge-base.py
```

#### 3. Run a showcase

```bash
pip install -r requirements.txt

cd 01_ambient_scribe   # or 02_document_intelligence, 03_research_agent
uvicorn main:app --reload --port 8000
# Open http://localhost:8000
```

## Scaleway services used

| Service | Purpose | Why |
|---------|---------|-----|
| **Generative APIs** | Chat, STT, vision, structured output | Serverless, OpenAI-compatible, pay-per-token |
| **GPU Instance (L4)** | Self-hosted vLLM serving Voxtral Realtime for WebSocket streaming STT | Low-latency realtime transcription on dedicated hardware |
| **Managed Inference** | Dedicated embedding model (BGE) on L4 GPU | Patient data never leaves your dedicated instance |
| **Managed PostgreSQL** | Vector store (pgvector) for RAG | Managed, European-hosted, supports vector search |
| **Object Storage** | Medical documents and audio files | S3-compatible, GDPR-compliant storage |

## Models

| Model | Parameters | Use |
|-------|-----------|-----|
| `mistral-small-3.2` | 24B (dense) | Chat, extraction, vision/OCR, agent, tool calling |
| `voxtral-small` | 24.3B | Speech-to-text (file upload) |
| `voxtral-mini-4b-realtime` | 4B | Realtime streaming STT via WebSocket (self-hosted on vLLM) |
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
- A [Scaleway account](https://account.scaleway.com/register) with API keys (€100 free credits on signup)

## License

Workshop materials for educational use.
