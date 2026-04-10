# Showcase 1 - Consultation Assistant

Diarized transcription of doctor-patient encounters with structured clinical note extraction, powered by **Voxtral** (speech-to-text with speaker diarization) and **Mistral** (structured extraction) on Scaleway Generative APIs.

## What it does

1. **Audio transcription with diarization** - upload an audio file and Voxtral transcribes the encounter, identifying speakers (Doctor / Patient).
2. **Clinical note extraction** - the transcript is sent to Mistral, which returns structured JSON (patient info, symptoms, medications, vitals, assessment, plan).

## Quick start

```bash
# From the repo root
cd 01_consultation_assistant

# Install dependencies (if not already)
pip install fastapi uvicorn python-dotenv openai

# Run the server
uvicorn main:app --reload --port 8000
```

Open **http://localhost:8000** and upload an audio file.

## Environment variables

| Variable | Description |
|---|---|
| `SCW_GENERATIVE_API_URL` | Scaleway Generative APIs base URL |
| `SCW_SECRET_KEY` | Scaleway API secret key |

Both variables are **required**. The showcase calls Scaleway Generative APIs for transcription (Voxtral) and extraction (Mistral).

## Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Serves the single-page frontend |
| `GET` | `/api/health` | Health check, returns model info |
| `POST` | `/api/transcribe` | Upload audio for diarized transcription via Voxtral |
| `POST` | `/api/extract` | Extract clinical note from transcript text via Mistral |
