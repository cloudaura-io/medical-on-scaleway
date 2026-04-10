# Scaleway Medical AI Lab

Workshop materials for a **[Scaleway](https://www.scaleway.com/) x [cloudaura.io](https://cloudaura.io/)** hands-on session on building healthcare AI applications. The lab demonstrates how to use Scaleway's sovereign European cloud infrastructure and [Mistral AI](https://mistral.ai/) models to solve real medical use cases: speech transcription, document understanding, and multi-domain research agents. All patient data stays in Europe, on infrastructure you control.

## What's in this repo

Three self-contained showcase applications, each demonstrating a different Scaleway AI capability applied to healthcare:

| # | Showcase | What it does | Scaleway services | Mistral models |
|---|----------|-------------|-------------------|----------------|
| 1 | **Consultation Assistant** | Transcribes doctor-patient conversations (file upload or realtime WebSocket streaming) and extracts structured clinical data | Generative APIs, GPU Instance (L4 + vLLM) | Voxtral (STT), Voxtral Mini 4B Realtime (streaming STT), Mistral Small 3.2 (extraction) |
| 2 | **Document Intelligence** | OCR on scanned medical documents, indexes them, answers questions with citations | Generative APIs, Managed Inference, PostgreSQL + pgvector, Object Storage | Mistral Small 3.2 (vision/OCR), BGE (embeddings) |
| 3 | **Research Agent** | Searches across pharmacology, cardiology, and clinical trial databases to answer complex medical questions | Generative APIs, Managed Inference, PostgreSQL + pgvector | Mistral Small 3.2 (agent + tool calling), BGE (embeddings) |

A Scaleway account with API keys is required to run the showcases. [Register for a free Scaleway account](https://account.scaleway.com/register) to get free credits.

## Architecture

Everything runs inside a **Scaleway VPC** with a single **HTTPS entry point** at `https://lab.cloudaura.io`. TLS is terminated at the Load Balancer. Caddy handles path-based routing on the app instance. No public IPs on any compute instance - all outbound goes through a NAT gateway.

```
https://lab.cloudaura.io
         |
    Load Balancer (LB-S, Let's Encrypt)
    |   :443 HTTPS (all user traffic)
    |   :80  HTTP  (ACME challenge)
    |   :2201 SSH  (app instance, TCP passthrough)
    |   :2202 SSH  (GPU instance, TCP passthrough)
         |
    VPC / Private Network 172.16.32.0/22
    |
    |-- NAT Gateway (VPC-GW-S) -- outbound internet for all instances
    |
    |-- App Instance (PLAY2-NANO, no public IP)
    |   Docker Compose: Caddy + 3 showcases
    |   /                         -> landing page
    |   /consultation-assistant/* -> FastAPI :8001
    |   /document-intelligence/*  -> FastAPI :8002
    |   /research-agent/*         -> FastAPI :8003
    |       |               |              |
    |       v               v              v
    |-- PostgreSQL      Managed        GPU Instance
    |   + pgvector      Inference      L4-1-24G
    |   :5432           BGE emb.       vLLM :8000
    |   (private)       (private)      (private)
    |
    External (via NAT gateway):
    Object Storage (S3)  |  Generative APIs  |  Container Registry
```

### Network security model

All instances have **no public IP**. Outbound internet goes through the NAT gateway. Security groups on each instance restrict inbound to the VPC CIDR (`172.16.32.0/22`) - only the Load Balancer (on the private network) can reach application ports. SSH access is via LB TCP passthrough on ports 2201 (app) and 2202 (GPU).

### AI services

| Service | Managed by | Infrastructure | Model | Params | Purpose |
|---------|-----------|----------------|-------|--------|---------|
| **Generative APIs** | Scaleway (serverless) | Shared, pay-per-token | Mistral Small 3.2 | 24B | Chat, extraction, vision/OCR, agent tool calling |
| **Generative APIs** | Scaleway (serverless) | Shared, pay-per-token | Voxtral Small | 24.3B | Speech-to-text (file upload mode) |
| **Managed Inference** | Scaleway (dedicated) | Dedicated L4 GPU | BGE Multilingual Gemma2 | ~9B | Text embeddings (3584-dim) for RAG |
| **Self-hosted vLLM** | You (raw GPU VM) | Dedicated L4 GPU | Voxtral Mini 4B Realtime | 4B | Real-time streaming STT via WebSocket |

### Docker deployment flow

A single `Dockerfile` builds one image for all three showcases. It's tagged three times and pushed to Scaleway Container Registry:

```
1. Your machine:   docker build -> tag 3x -> push to registry
2. App instance:   cloud-init: wait for network -> install Docker -> registry login
                   -> docker compose pull -> docker compose up (~2 min)
```

Cloud-init retries `docker compose pull` every 30 seconds until images become available (they're pushed after `tofu apply` completes).

### How each showcase connects

#### Consultation Assistant

Audio -> Generative APIs (Voxtral STT) -> transcript -> Generative APIs (Mistral) -> clinical JSON. Live mic mode streams via WebSocket to the GPU vLLM instance on the private network.

![Consultation Assistant architecture](docs/usecase1.webp)

> **Models:** Voxtral Small (24.3B) · Voxtral Mini 4B Realtime (4B) · Mistral Small 3.2 (24B)

#### Document Intelligence

PDF -> Object Storage (S3 via NAT) -> Generative APIs (Mistral vision/OCR) -> Managed Inference (BGE embeddings, private) -> PostgreSQL pgvector (private) -> Generative APIs (Mistral cited answer).

![Document Intelligence architecture](docs/usecase2.webp)

> **Models:** Mistral Small 3.2 (24B) · BGE Multilingual Gemma2 (~9B)

#### Research Agent

Query -> Generative APIs (Mistral agent + tool calling) -> Managed Inference (BGE, private) + pgvector (private) -> verified answer.

![Research Agent architecture](docs/usecase3.webp)

> **Models:** Mistral Small 3.2 (24B) · BGE Multilingual Gemma2 (~9B)

## Quick start

### Automated setup (recommended)

```bash
bash scripts/setup.sh
```

Provisions infrastructure, builds and pushes Docker images, generates `.env`, and waits for services to come online. Database schema is created automatically by the backend on first request.

### Manual setup

```bash
# 1. Provision infrastructure
cp infrastructure/terraform.tfvars.example infrastructure/terraform.tfvars
# Edit with your Scaleway credentials
cd infrastructure && tofu init && tofu apply

# 2. Set up DNS: A record lab.cloudaura.io -> LB IP (tofu output lb_public_ip)
#    Cloudflare proxy must be OFF (DNS-only) for Let's Encrypt

# 3. Build and push Docker images
bash scripts/build-push-images.sh

# 4. Generate local .env
bash scripts/generate-env.sh

# 5. Seed the knowledge base (after app instance boots)
ssh -i ~/.ssh/id_ed25519_scaleway -p 2201 root@lab.cloudaura.io \
  docker compose -f /opt/app/docker-compose.yaml exec showcase2 \
  python scripts/load-knowledge-base.py
```

### Access

```
https://lab.cloudaura.io/                        Landing page
https://lab.cloudaura.io/consultation-assistant/  Consultation Assistant
https://lab.cloudaura.io/document-intelligence/   Document Intelligence
https://lab.cloudaura.io/research-agent/          Research Agent
```

### SSH (debugging)

```bash
ssh -i ~/.ssh/id_ed25519_scaleway -p 2201 root@lab.cloudaura.io   # app instance
ssh -i ~/.ssh/id_ed25519_scaleway -p 2202 root@lab.cloudaura.io   # GPU instance
```

### Redeploy after code changes

```bash
docker build --no-cache -t medical-lab-base:latest .
bash scripts/build-push-images.sh
cd infrastructure && tofu apply -replace=scaleway_instance_server.app
```

### Local development

```bash
pip install -r requirements.txt
cd 01_consultation_assistant && uvicorn main:app --reload --port 8000
```

## Medical AI safety

All showcases implement layered trustworthiness patterns:

- **Grounded RAG with citations**: every medical claim references a source document
- **Structured output validation**: Mistral's native JSON schema mode guarantees valid data
- **Human-in-the-loop**: AI outputs are suggestions, not decisions
- **Chain-of-Verification**: claims are independently fact-checked against the knowledge base
- **Audit logging**: all queries, responses, and sources are recorded

## Prerequisites

- Docker (for building and pushing showcase images)
- OpenTofu 1.5+ (for infrastructure provisioning)
- Python 3.11+ (`pip install -r requirements.txt`)
- A [Scaleway account](https://account.scaleway.com/register) with API keys

## License

Workshop materials for educational use.
