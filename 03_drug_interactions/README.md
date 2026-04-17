# Showcase 3 — Drug Interactions Checker

A **ReAct agent** (Think → Act → Observe) that analyzes drug-drug and drug-population interactions against FDA-sourced drug labels, streaming every reasoning step to the UI via SSE.

![Drug Interactions UI](../docs/drug_interactions.png)

## What it does

1. **Input** — a list of medications and an optional patient population (`pregnancy`, `pediatric`, `geriatric`, `renal`, `hepatic`).
2. **ReAct loop** — Mistral Small 3.2 reasons over the query, picks a tool, observes the result, and iterates. Each step is streamed to the browser as it happens.
3. **Grounded answer** — the final report is synthesized from retrieved FDA label excerpts, with per-claim citations back to the original `openfda` record (clickable link to `api.fda.gov`).

## Agent tools

| Tool | Purpose |
|---|---|
| `search_drug_kb` | Embedding similarity search across all drug-label chunks |
| `lookup_interactions` | Targeted retrieval of `drug_interactions` label sections |
| `lookup_population_warnings` | Retrieval of pregnancy / pediatric / geriatric / renal / hepatic warnings |
| `flag_severity` | Re-classify findings by severity (critical / major / moderate / minor) |
| `summarize_evidence` | Synthesize the final report with source attribution |

## Models & services

| Role | Scaleway Service | Model | Size |
|---|---|---|---|
| Agent reasoning + tool calling | Generative APIs (serverless) | `mistral-small-3.2-24b-instruct-2506` | 24B |
| Embeddings | Managed Inference (dedicated L4 GPU) | `qwen3-embedding-8b` | 8B, 768-dim |
| Knowledge base | Managed PostgreSQL (DB-DEV-S) | `pgvector` | — |

The knowledge base is populated from **openFDA Structured Product Labeling (SPL)** snapshots — chunked by label section (indications, contraindications, drug interactions, warnings, pregnancy, etc.), embedded with Qwen3, and indexed in pgvector.

## Prerequisites

- Scaleway API key with Generative APIs + Managed Inference access
- PostgreSQL with `pgvector` (populated with FDA label chunks — the repo's terraform seeds this)
- Environment variables: `SCW_GENERATIVE_API_URL`, `SCW_SECRET_KEY`, `SCW_INFERENCE_ENDPOINT`, `DATABASE_URL`

## Quick start

```bash
# From the repo root
cd 03_drug_interactions
pip install -r ../requirements.txt
uvicorn main:app --reload --port 8003
# Open http://localhost:8003
```

The UI ships with six one-click sample combinations (e.g. *Sertraline + Tramadol* — serotonin syndrome + CYP2D6, *Warfarin + Sertraline* — CYP2C9 bleeding risk) to demonstrate the agent without hand-typing medication names.

## Endpoints

- `GET /` — frontend
- `GET /api/health` — health check
- `GET /api/sample-queries` — pre-defined demo combinations
- `POST /api/analyze` — run the ReAct loop, streaming `think`/`act`/`observe` steps, findings, and a final report via SSE
