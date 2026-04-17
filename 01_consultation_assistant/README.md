# Showcase 1 — Consultation Assistant

Diarized transcription of doctor-patient encounters with structured clinical note extraction. Powered by **Voxtral** (speech-to-text) and **Mistral Small 3.2** (structured extraction) on Scaleway.

![Consultation Assistant UI](../docs/transcription_example.png)

## What it does

1. **File-upload transcription with diarization** — upload an audio file, Voxtral Small (24B) transcribes it via Scaleway Generative APIs, and a second pass with Mistral Small 3.2 labels each turn as `Doctor:` or `Patient:`.
2. **Real-time streaming transcription** — browser mic → WebSocket (`/ws/transcribe`) → self-hosted **Voxtral Mini 4B Realtime** running on a Scaleway L4 GPU via vLLM. Partial transcripts stream back as the user speaks.
3. **Clinical note extraction** — the transcript is sent to Mistral Small 3.2 with a JSON schema, returning structured data (patient info, symptoms, medications, vitals, assessment, plan).

## Models

| Role | Model | Size | Backend |
|---|---|---|---|
| Batch STT + diarization | `voxtral-small-24b-2507` | 24.3B | Scaleway Generative APIs (serverless) |
| Real-time streaming STT | `Voxtral-Mini-4B-Realtime-2602` | 4B | Self-hosted vLLM on Scaleway L4-1-24G |
| Clinical extraction | `mistral-small-3.2-24b-instruct-2506` | 24B | Scaleway Generative APIs (serverless) |

## Quick start

```bash
# From the repo root
cd 01_consultation_assistant

# Install dependencies
pip install -r ../requirements.txt

# Run the server
uvicorn main:app --reload --port 8001
```

Open **http://localhost:8001** and upload an audio file (or use the live mic tab if `SCW_VOXTRAL_REALTIME_ENDPOINT` is set).

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `SCW_GENERATIVE_API_URL` | yes | Scaleway Generative APIs base URL |
| `SCW_SECRET_KEY` | yes | Scaleway API secret key |
| `SCW_VOXTRAL_REALTIME_ENDPOINT` | for live mic | URL of the vLLM Voxtral Realtime instance (private VPC in prod) |

## Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Single-page frontend |
| `GET` | `/api/health` | Health check, returns model info |
| `POST` | `/api/transcribe` | Upload audio for diarized transcription (Voxtral Small) |
| `POST` | `/api/extract` | Extract structured clinical note from transcript (Mistral Small 3.2) |
| `WS` | `/ws/transcribe` | Real-time streaming STT (Voxtral Mini 4B Realtime on vLLM) |
