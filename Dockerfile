FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY static/ ./static/
COPY 01_consultation_assistant/ ./01_consultation_assistant/
COPY 02_document_intelligence/ ./02_document_intelligence/
COPY 03_drug_interactions/ ./03_drug_interactions/
COPY scripts/ ./scripts/
COPY workshop/data/ ./workshop/data/
