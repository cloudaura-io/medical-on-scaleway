# Showcase 3 — Cross-domain Medical Research Agent

Tool-calling agent that searches across pharmacology, cardiology, and clinical trial knowledge domains, then verifies each claim using Chain-of-Verification (CoVe).

## Prerequisites

Scaleway API keys and a pgvector knowledge base must be configured. See `src/config.py` for the required environment variables.

## Run

```bash
cd 03_research_agent
uvicorn main:app --reload --port 8002
```

Open [http://localhost:8002](http://localhost:8002).

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Serve the single-page app |
| POST | `/api/research` | Run the agent (SSE stream) |
| GET | `/api/domains` | Knowledge domain metadata |
| GET | `/api/sample-queries` | Sample research questions |
| GET | `/api/health` | Health check |
