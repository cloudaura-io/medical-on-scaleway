# Scaleway Medical AI Lab - Implementation Plan

## Context

Workshop for healthcare professionals (directors, tech leads, innovation officers) who are AI beginners. Two distinct parts:

1. **3 Showcase Demos** - Pre-built, polished demos run by presenters to show Scaleway AI capabilities. Each uses different Mistral models and Scaleway services.
2. **1 Interactive Lab** - Students build a working AI agent step-by-step on their laptops. Designed for easy-to-medium AI knowledge. Progressive difficulty: basic API call -> structured output -> RAG -> agent -> safety.

---

## Part A: Three Showcase Demos

Pre-built by us, run by presenters during the workshop. Audience watches, asks questions. Each demo is a standalone web app (Python FastAPI backend + single-page HTML/CSS/JS frontend). No React - pure HTML with beautiful, hand-crafted CSS and vanilla JS. Backend serves API endpoints that the frontend calls.

### Showcase 1: Doctor Assistant (Speech -> Structured Record)

**Story**: A doctor records a 5-minute patient consultation. AI transcribes it, extracts structured medical data, and produces a draft clinical note - all in real-time.

**Models & Services**:
| What | Scaleway Service | Model |
|---|---|---|
| Speech-to-Text | Generative APIs | `voxtral-small-24b-2507` |
| Clinical extraction | Generative APIs | `mistral-small-3.2` |
| Structured output | Generative APIs | `mistral-small-3.2` (JSON mode) |

**Demo flow**:
1. Presenter plays a synthetic doctor-patient audio recording (patient with chest pain, diabetes history, on metformin)
2. Voxtral transcribes in real-time -> raw transcript appears on screen
3. Mistral Small 3.2 extracts structured data using native JSON schema mode:
   - Patient demographics, chief complaint, history of present illness
   - Current medications, allergies, vital signs mentioned
   - Assessment & plan
4. Output: side-by-side view - raw transcript on the left, structured clinical note on the right
5. **Safety highlight**: Show that Mistral's structured output guarantees valid JSON matching the schema - no post-processing needed. Every field is traceable to a specific part of the transcript

**What it showcases**: Voxtral STT quality, Mistral structured output, Scaleway Generative APIs speed, medical data validation

---

### Showcase 2: Medical Document Intelligence (OCR -> RAG)

**Story**: A hospital has stacks of scanned medical documents (lab reports, discharge summaries, imaging reports). AI reads them, understands them, and makes them searchable with natural language.

**Models & Services**:
| What | Scaleway Service | Model |
|---|---|---|
| Document OCR/Vision | Generative APIs | `pixtral-12b-2409` |
| Embeddings | Managed Inference (L4 GPU) | `bge-multilingual-gemma2` - dedicated instance for patient data privacy |
| Text processing | Generative APIs | `mistral-small-3.2` |
| Embeddings | Generative APIs | `bge-multilingual-gemma2` |
| Vector store | Managed PostgreSQL | pgvector |
| Document storage | Object Storage | S3-compatible |

**Demo flow**:
1. Presenter uploads 3-4 sample medical PDFs (lab report with blood work, discharge summary, radiology report)
2. Pixtral (via Generative APIs) reads each page -> extracts text + understands tables/layouts
3. Extracted text is chunked, embedded, stored in pgvector
4. Presenter asks natural language questions:
   - "What were the patient's HbA1c levels across all reports?"
   - "Summarize the discharge recommendations"
   - "Are there any abnormal lab values?"
5. RAG responds with answers + exact citations (document name, page number, highlighted passage)
6. **Safety highlight**: Every answer points back to a specific source document. Ask something not in the documents -> system says "No evidence found in uploaded documents"

**What it showcases**: Pixtral vision/OCR via Generative APIs, embeddings on Managed Inference (data sovereignty - dedicated GPU for patient data, never touches shared infrastructure), pgvector RAG, Scaleway Object Storage, citation-grounded responses

---

### Showcase 3: Cross-domain Medical Research Agent

**Story**: A researcher is investigating whether a new diabetes drug interacts with common cardiac medications. Instead of searching 5 different databases manually, they ask one AI agent that searches across pharmacology, cardiology guidelines, and clinical trial data simultaneously.

**Models & Services**:
| What | Scaleway Service | Model |
|---|---|---|
| Research synthesis | Generative APIs | `mistral-small-3.2` |
| Tool calling | Generative APIs | `mistral-small-3.2` (function calling) |
| Embeddings | Managed Inference (L4 GPU) | `bge-multilingual-gemma2` - patient data stays on dedicated instance |
| Multi-domain vector store | Managed PostgreSQL | pgvector (separate collections per domain) |

**Demo flow**:
1. Knowledge base pre-loaded with documents across 3 domains:
   - Pharmacology (drug interactions, mechanisms of action)
   - Cardiology guidelines (ACC/AHA, ESC)
   - Clinical trial summaries (synthetic, realistic)
2. Presenter asks: "Patient is on empagliflozin for diabetes. Cardiologist wants to start amiodarone. Any concerns?"
3. Agent decides which tools to call:
   - `search_pharmacology("empagliflozin amiodarone interaction")` -> retrieves drug interaction data
   - `search_cardiology("amiodarone prescribing guidelines")` -> retrieves cardiology guidelines
   - `search_clinical_trials("SGLT2 inhibitors antiarrhythmic drugs")` -> retrieves trial data
4. Agent synthesizes across domains -> produces a structured research summary with citations from all three sources
5. Chain-of-Verification: each claim is checked against sources -> labeled VERIFIED / UNVERIFIED
6. **Safety highlight**: Show the verification step making AI reasoning transparent. Show that unverified claims are flagged, not hidden.

**What it showcases**: Multi-domain RAG, Mistral function calling/tool use, Chain-of-Verification, cross-domain synthesis, Scaleway PostgreSQL pgvector

---

## Showcase UI Design

Tech stack for all 3 showcases: **Python FastAPI** backend + **single-page HTML/CSS/JS** frontend. No React, no npm, no build step. One `index.html` per showcase, served by FastAPI. Backend exposes REST/SSE endpoints. Frontend uses `fetch()` and `EventSource` for streaming.

### Showcase 1 UI: Doctor Assistant

**Aesthetic direction**: Clinical-editorial. Think high-end medical journal meets modern dashboard. Dark theme (deep navy `#0a1628` background) with warm amber accents (`#e8a838`) for highlights. Clean, confident, authoritative.

**Typography**: `DM Serif Display` for headings (medical authority), `IBM Plex Mono` for transcript/data (clinical precision).

**Layout** (single page, no scrolling):
```
┌-----------------------------------------------------------------┐
|  DOCTOR ASSISTANT                            [● Recording]      |
|  Scaleway × Mistral                          [▶ Play Sample]    |
|------------------------------┬------------------------------------┤
|                            |                                    |
|   LIVE TRANSCRIPT          |   CLINICAL NOTE                    |
|                            |                                    |
|   Words appear here as     |   ┌- Patient -----------------┐   |
|   Voxtral transcribes.     |   | Jan K., 58M               |   |
|   Current word highlighted |   | Chief Complaint: ...       |   |
|   in amber.                |   |-----------------------------┘   |
|                            |                                    |
|   Waveform visualization   |   ┌- Medications ------------┐   |
|   at the bottom of this    |   | • Metformin 1000mg BID   |   |
|   panel showing audio      |   | • Lisinopril 10mg QD     |   |
|   being processed.         |   |-----------------------------┘   |
|                            |                                    |
|                            |   ┌- Assessment & Plan ------┐   |
|                            |   | ...                       |   |
|                            |   |-----------------------------┘   |
|                            |                                    |
|------------------------------┴------------------------------------┤
|  ⚡ Processing: 3.2s  |  Model: voxtral-small  |  Validated ✓  |
|-------------------------------------------------------------------┘
```

**Key interactions**:
- Click "Play Sample" -> audio waveform animates, transcript streams in word-by-word (SSE from backend)
- As transcript completes, right panel cards animate in with staggered fade-up (200ms delay per card)
- Each structured field has a subtle amber underline linking back to the transcript source (hover to highlight the source text on the left)
- Bottom status bar shows real-time processing metrics
- Validation badge pulses green when structured output schema is satisfied

**Backend endpoints**:
- `POST /api/transcribe` - accepts audio file, returns SSE stream of transcript chunks
- `POST /api/extract` - accepts transcript text, returns structured clinical note JSON
- `GET /api/health` - health check

**Files**:
```
01_consultation_assistant/
|---- main.py              # FastAPI app
|---- static/
|   |---- index.html       # Single page
|   |---- style.css        # All styles
|   |---- app.js           # Vanilla JS (fetch, SSE, animations)
|---- README.md
```

---

### Showcase 2 UI: Medical Document Intelligence

**Aesthetic direction**: Archival-modern. Think digitized medical records - the feeling of paper being understood by a machine. Light warm background (`#f5f0e8`, parchment) with deep teal accents (`#1a5c5e`). Subtle paper texture overlay.

**Typography**: `Fraunces` for headings (editorial weight), `JetBrains Mono` for extracted text/data (technical precision).

**Layout** (three-phase flow - upload -> process -> query):
```
┌-----------------------------------------------------------------┐
|  DOCUMENT INTELLIGENCE                    Powered by Pixtral    |
|  -------------------------------------------------------------  |
|                                                                 |
|  Phase 1: UPLOAD          Phase 2: PROCESS       Phase 3: ASK   |
|  ---------------          ----------------       -----------    |
|                                                                 |
|  ┌---------------------------------------------------------┐   |
|  |                                                         |   |
|  |   [Drop PDFs here or click to upload]                   |   |
|  |                                                         |   |
|  |   📄 lab_report.pdf          ✓ OCR complete            |   |
|  |   📄 discharge_summary.pdf   ⟳ Processing...           |   |
|  |   📄 radiology_report.pdf    ○ Queued                  |   |
|  |                                                         |   |
|  |-----------------------------------------------------------┘   |
|                                                                 |
|  ┌--------------------------┬------------------------------┐   |
|  |  DOCUMENT VIEWER         |  AI RESPONSE                 |   |
|  |                          |                              |   |
|  |  [PDF page rendered      |  "The patient's HbA1c was   |   |
|  |   with highlighted       |   7.2% - above the target   |   |
|  |   regions that Pixtral   |   of <7% for diabetics.     |   |
|  |   extracted text from]   |   [Source: lab_report, p.1]" |   |
|  |                          |                              |   |
|  |  Page 1 of 3  ◄ ►       |  --------------------------  |   |
|  |                          |  💬 Ask: [________________]  |   |
|  |----------------------------┴------------------------------┘   |
|                                                                 |
|  Chunks indexed: 47  |  Pixtral (Gen API) | Embeddings (Managed Inf.)|
|-------------------------------------------------------------------┘
```

**Key interactions**:
- Drag-and-drop PDF upload with paper-drop animation (subtle bounce + shadow)
- Processing phase: each PDF shows a progress bar as Pixtral OCR runs, extracted text preview appears
- After processing, document viewer on left shows the actual PDF page with golden highlight boxes around extracted regions
- Chat input on right - type a question, response streams in with citations
- Click a citation -> left panel scrolls to the exact page and highlights the passage (smooth scroll + pulse animation)
- Phase transitions slide horizontally with easing

**Backend endpoints**:
- `POST /api/upload` - accepts PDF, stores in Object Storage, returns doc_id
- `POST /api/process/{doc_id}` - runs Pixtral OCR, chunks, embeds, stores in pgvector. Returns SSE progress
- `POST /api/query` - RAG query, returns cited response
- `GET /api/documents` - list processed documents

**Files**:
```
02_document_intelligence/
|---- main.py              # FastAPI app
|---- static/
|   |---- index.html
|   |---- style.css
|   |---- app.js
|---- README.md
```

---

### Showcase 3 UI: Cross-domain Research Agent

**Aesthetic direction**: Research-lab futuristic. Think mission control for medical research. Dark background (`#0d1117`) with phosphor green (`#00d68f`) and electric blue (`#58a6ff`) for the two main data streams. Node/graph visual metaphor - knowledge domains are visible "nodes" that light up when the agent queries them.

**Typography**: `Space Mono` for the agent log/terminal feel, `Sora` for headings and UI labels (geometric, modern).

**Layout** (agent-centric - watch the AI think):
```
┌-----------------------------------------------------------------┐
|  RESEARCH AGENT                              ◉ Agent Active     |
|  Cross-domain Medical Intelligence                              |
|-------------------------------------------------------------------┤
|                                                                 |
|  ┌- QUERY --------------------------------------------------┐  |
|  |  "Patient on empagliflozin for diabetes. Cardiologist     |  |
|  |   wants to start amiodarone. Any concerns?"        [Run ▶]|  |
|  |------------------------------------------------------------┘  |
|                                                                 |
|  ┌- KNOWLEDGE DOMAINS --------------------------------------┐  |
|  |                                                           |  |
|  |    ┌----------┐     ┌----------┐     ┌----------┐       |  |
|  |    | PHARMA-  |----->| CARDIO-  |----->| CLINICAL |       |  |
|  |    | COLOGY   |     | LOGY     |     | TRIALS   |       |  |
|  |    |  ◉ 12    |     |  ◉ 8     |     |  ◉ 5     |       |  |
|  |    |  chunks  |     |  chunks  |     |  chunks  |       |  |
|  |    |------------┘     |------------┘     |------------┘       |  |
|  |    (nodes glow green/blue when agent queries them)       |  |
|  |------------------------------------------------------------┘  |
|                                                                 |
|  ┌- AGENT LOG ------┐  ┌- VERIFIED FINDINGS ----------------┐ |
|  |                   |  |                                     | |
|  |  > Thinking...    |  |  ✓ VERIFIED: Empagliflozin has no  | |
|  |  > Tool call:     |  |    direct interaction with          | |
|  |    search_pharma  |  |    amiodarone [Pharma DB, §4.2]    | |
|  |    ("empaglifloz  |  |                                     | |
|  |     in amiodaro   |  |  ✓ VERIFIED: Amiodarone requires   | |
|  |     ne")          |  |    baseline ECG and thyroid         | |
|  |  > 12 chunks      |  |    monitoring [ACC/AHA, Ch.7]      | |
|  |    retrieved       |  |                                     | |
|  |  > Tool call:     |  |  ⚠ UNVERIFIED: Combined QT         | |
|  |    search_cardio  |  |    prolongation risk - insufficient | |
|  |    ("amiodarone   |  |    evidence in knowledge base       | |
|  |     guidelines")  |  |                                     | |
|  |  > Synthesizing...|  |  -- Disclaimer ------------------  | |
|  |  > Verifying      |  |  AI-generated. Verify with medical | |
|  |    claims...      |  |  professionals before clinical use. | |
|  |---------------------┘  |---------------------------------------┘ |
|                                                                 |
|  Mistral Small 3.2  |  3 domains  |  25 chunks retrieved  |  CoVe |
|-------------------------------------------------------------------┘
```

**Key interactions**:
- Type or select a pre-built research question -> click "Run"
- Knowledge domain nodes light up in sequence as the agent queries them (green pulse animation)
- Agent log on the left shows tool calls in real-time (terminal-style monospace, text streams in)
- Verified findings appear on the right with staggered animation - green checkmarks slide in for verified, amber warnings for unverified
- Click any citation -> expands inline to show the full source passage
- Domain nodes show chunk count badges updating in real-time
- Unverified claims have a subtle pulsing amber border - visually distinct from verified

**Backend endpoints**:
- `POST /api/research` - accepts query, returns SSE stream of agent steps (tool calls, retrievals, synthesis, verification)
- `GET /api/domains` - list knowledge domains with stats
- `GET /api/sample-queries` - pre-built research questions for demo

**Files**:
```
03_research_agent/
|---- main.py              # FastAPI app
|---- static/
|   |---- index.html
|   |---- style.css
|   |---- app.js
|---- README.md
```

---

## UI Technical Stack (all showcases)

| Component | Choice | Why |
|---|---|---|
| Backend | FastAPI | Async, SSE support, minimal boilerplate, Python-native |
| Frontend | Vanilla HTML/CSS/JS | No build step, no npm, instant load, POC-appropriate |
| Streaming | Server-Sent Events (SSE) | Native browser support, perfect for LLM token streaming |
| Fonts | Google Fonts | Free, no licensing issues, loaded via CDN |
| Animations | CSS `@keyframes` + `animation-delay` | No JS animation libraries needed |
| Serving | FastAPI `StaticFiles` | Backend serves the frontend, single `uvicorn` process |

Each showcase runs with: `cd 01_consultation_assistant && uvicorn main:app --reload`

---

## Part B: Interactive Lab - "Build a Clinical Note Assistant"

Students build a working AI agent on their laptops. Each step builds on the previous one. Notebooks are guided: most cells are pre-written with comments, key cells have `# TODO` sections where students write 1-5 lines of code.

### Lab Scenario

> You are a developer at a hospital. Doctors write messy, unstructured clinical notes after each consultation. Your task: build an AI assistant that helps doctors by structuring their notes, checking them against medical guidelines, and producing a verified clinical summary.

**Sample clinical note** (provided in `data/`):
```
Patient Jan K., 58M, came in complaining of chest tightness for 3 days,
worse on exertion. History of T2DM x 10 years, HTN. Currently on
metformin 1000mg BID, lisinopril 10mg daily. BP today 155/95.
Mentioned occasional dizziness when standing up. No family history of
cardiac disease. Non-smoker. ECG shows sinus rhythm, no ST changes.
Plan: order troponin, lipid panel, stress test. Consider adding
statin. Follow up in 1 week.
```

### Infrastructure (OpenTofu)

Students run `tofu apply` to provision:
- Managed PostgreSQL (DB-DEV-S) with pgvector
- Object Storage bucket (for knowledge base documents)

Generative APIs require only an API key (no infra to provision).

### Lab Notebooks

#### Lab 0: Setup & First API Call (~15 min)
`notebooks/lab_00_setup.ipynb`

- Clone repo, pip install requirements
- Configure `.env` (Scaleway API key, DB connection from OpenTofu output)
- **Cell 1**: Create OpenAI client pointing to `https://api.scaleway.ai/v1`
- **Cell 2**: First chat completion - ask Mistral "What are the common symptoms of type 2 diabetes?"
- **Cell 3**: Verify PostgreSQL connection, enable pgvector extension
- **Key takeaway**: Scaleway Generative APIs are OpenAI-compatible. One line change to switch from OpenAI to Scaleway.

#### Lab 1: Understanding the Clinical Note (~15 min)
`notebooks/lab_01_clinical_understanding.ipynb`

- **Cell 1**: Load the sample clinical note from `data/`
- **Cell 2**: Ask Mistral to summarize the note (basic prompt)
- **Cell 3**: Ask Mistral to summarize with a medical system prompt - compare quality
- **Cell 4** (TODO): Write a system prompt that instructs the model to identify the top 3 clinical concerns for this patient
- **Cell 5**: Discuss: the model "knows" medical concepts but might hallucinate details. How do we make it trustworthy?
- **Key takeaway**: Prompt engineering matters. System prompts shape behavior. But LLMs can hallucinate - we need more.

#### Lab 2: Structured Data Extraction (~20 min)
`notebooks/lab_02_structured_extraction.ipynb`

- **Cell 1**: Introduction to Mistral's structured output - explain `response_format: {"type": "json_schema"}`
- **Cell 2**: Define a JSON schema for clinical data extraction:
  ```json
  {
    "patient_name": "string",
    "age": "integer",
    "sex": "M | F",
    "chief_complaint": "string",
    "symptoms": [{"description": "string", "duration": "string", "severity": "mild | moderate | severe"}],
    "current_medications": [{"name": "string", "dosage": "string", "frequency": "string"}],
    "vitals": {"key": "value"},
    "assessment": "string",
    "plan": ["string"]
  }
  ```
- **Cell 3**: Call Mistral with the schema + clinical note -> get guaranteed valid structured JSON back
- **Cell 4** (TODO): Extend the schema to also extract potential drug interactions between listed medications
- **Cell 5**: Show what happens without structured output (raw text, inconsistent format) vs with it (clean JSON every time)
- **Key takeaway**: Mistral's native structured output on Scaleway guarantees valid JSON. No parsing, no regex, no extra libraries - the model handles it.

#### Lab 3: RAG - Building a Medical Knowledge Base (~25 min)
`notebooks/lab_03_rag_knowledge_base.ipynb`

- **Cell 1**: Load 4 knowledge base documents from `data/knowledge_base/`:
  - `diabetes_guidelines.md` - Type 2 diabetes management guidelines
  - `hypertension_guidelines.md` - Hypertension treatment protocols
  - `drug_interactions.md` - Common drug interaction database
  - `cardiac_workup.md` - Chest pain evaluation guidelines
- **Cell 2**: Chunk documents (500 chars, 100 overlap) - show what chunks look like
- **Cell 3**: Create embeddings via Scaleway Generative APIs
- **Cell 4**: Store in pgvector - show the SQL, explain cosine similarity
- **Cell 5** (TODO): Write a retrieval function - given a query, embed it, search pgvector, return top-5 chunks with source metadata
- **Cell 6**: Test retrieval: "What is the target blood pressure for a diabetic patient?"
- **Cell 7**: Compare: same question to bare Mistral (no RAG) vs with RAG context. Show how RAG grounds the response and adds citations.
- **Key takeaway**: RAG = LLM anchored to YOUR data. It can only cite what you give it. This is how you make medical AI trustworthy.

#### Lab 4: Building a Tool-Calling Agent (~25 min)
`notebooks/lab_04_agent.ipynb`

- **Cell 1**: Introduction to function calling - define tools as Python functions:
  ```python
  def search_guidelines(query: str) -> list[dict]:
      """Search medical guidelines knowledge base."""
      # Uses RAG pipeline from Lab 3

  def extract_patient_data(clinical_note: str) -> ClinicalNote:
      """Extract structured patient data from clinical note."""
      # Uses extraction from Lab 2

  def check_drug_interaction(drug1: str, drug2: str) -> dict:
      """Check for interactions between two drugs."""
      # RAG search specifically in drug_interactions collection
  ```
- **Cell 2**: Register tools with Mistral using OpenAI-compatible function calling format
- **Cell 3**: Build the agent loop:
  1. Send clinical note + tools to Mistral
  2. Model decides which tools to call (observe the reasoning!)
  3. Execute tool calls, return results
  4. Model synthesizes a final clinical summary
- **Cell 4** (TODO): Add a `check_vital_signs(vitals: dict)` tool that flags abnormal values (BP > 140/90, etc.) - register it and re-run the agent
- **Cell 5**: Run the full agent - observe it calling multiple tools, cross-referencing results
- **Key takeaway**: Agents = LLM that decides what to do. It picks the right tools, combines results, and reasons over them. This is the foundation of useful medical AI.

#### Lab 5: Making It Safe - Guardrails & Human Review (~20 min)
`notebooks/lab_05_safety.ipynb`

- **Cell 1**: Add citation enforcement - modify the system prompt to require `[Source: document, section]` for every medical claim
- **Cell 2**: Run the agent with citation enforcement - observe inline citations in output
- **Cell 3**: Add mandatory disclaimer wrapper - every output starts with "AI-generated suggestion. Always verify with qualified medical professionals."
- **Cell 4**: Human-in-the-Loop simulation:
  ```python
  def human_review(draft_summary: dict) -> dict:
      """Pause and show the draft to the doctor for approval."""
      print("=== DRAFT CLINICAL SUMMARY ===")
      print(draft_summary)
      approval = input("Doctor, do you approve? (yes/edit/reject): ")
      ...
  ```
- **Cell 5** (TODO): Try to break the agent - ask it: "Prescribe the strongest painkiller for this patient." Observe how the RAG grounding + guardrails prevent dangerous output (model should refuse because no evidence in knowledge base supports prescribing)
- **Cell 6**: Audit logging - show how every query, tool call, and response is logged with timestamps
- **Key takeaway**: Medical AI is NOT about the model being smart. It's about LAYERS of safety: citations, validation, human review, audit trails. This is what separates a demo from a production system.

#### Lab 6: Full Pipeline & Wrap-up (~15 min)
`notebooks/lab_06_full_pipeline.ipynb`

- **Cell 1**: Run the complete pipeline end-to-end:
  ```
  Raw clinical note
      -> Structured extraction (Lab 2)
      -> Guideline search (Lab 3)
      -> Drug interaction check (Lab 4)
      -> Agent synthesis (Lab 4)
      -> Citation enforcement (Lab 5)
      -> Human review gate (Lab 5)
      -> Final verified clinical summary
  ```
- **Cell 2**: Show the final output - a structured, cited, human-approved clinical summary
- **Cell 3**: Discussion prompts:
  - What would you add for production? (monitoring, continuous evaluation, FHIR integration)
  - EU AI Act: healthcare AI is "high-risk" - what architectural patterns support compliance?
  - Data sovereignty: why Scaleway's European cloud matters for patient data
- **Cell 4**: OpenTofu destroy - clean up resources

---

## Architecture Overview

```
┌-----------------------------------------------------------------┐
|                    Scaleway Cloud (fr-par)                       |
|                                                                 |
|  ┌------------------┐  ┌------------------┐  ┌--------------┐  |
|  | Generative APIs   |  | Managed Inference |  | Object       |  |
|  | (serverless)      |  | (dedicated GPU)   |  | Storage (S3) |  |
|  |                   |  |                   |  |              |  |
|  | • Mistral Sm 3.2  |  | • BGE Embeddings  |  | Audio files  |  |
|  | • Voxtral Small   |  |   (L4 GPU)        |  | Medical PDFs |  |
|  | • Pixtral 12B     |  |   Patient data     |  | Knowledge    |  |
|  | • BGE Embeddings  |  |   stays private    |  | base docs    |  |
|  |----------┬---------┘  |----------┬----------┘  |--------┬-------┘  |
|           |                     |                     |          |
|  ┌--------┴---------------------┴---------------------┴-------┐  |
|  |              Managed PostgreSQL + pgvector                  |  |
|  |              (Vector store for RAG)                         |  |
|  |--------------------------------------------------------------┘  |
|-------------------------------------------------------------------┘

**Models & Pricing:**
| Model | Params | Type | Scaleway Price | Used For |
|---|---|---|---|---|
| `mistral-small-3.2` | 24B | Dense (chat + vision) | EUR 0.15 / 0.35 per 1M tokens (in/out) | Chat, extraction, agent, tool calling |
| `voxtral-small` | 24.3B | Dense + Whisper encoder | EUR 0.003/audio-min + text tokens | Speech-to-text (Showcase 1) |
| `pixtral-12b` | 12.4B | Dense + ViT encoder | EUR 0.20 / 0.20 per 1M tokens | OCR/vision (Showcase 2) |
| `bge-multilingual-gemma2` | ~9B | Dense (embeddings) | Managed Inference: L4 @ EUR 0.93/hr | Embeddings for RAG (dedicated instance for patient data privacy) |

  SHOWCASES (presenters)          |        LAB (students)
  ---------------------           |        ----------------
  • Voxtral STT                   |        • Generative APIs only
  • Pixtral OCR (Gen API)          |        • PostgreSQL + pgvector
  • Multi-domain RAG              |        • Object Storage
  • Streamlit apps                |        • Jupyter notebooks
```

---

## Repository Structure

```
scaleway-medical-lab/
|---- README.md
|---- .gitignore
|---- .env.example
|---- requirements.txt
|
|---- infrastructure/
|   |---- main.tf                        # PostgreSQL + Object Storage + Managed Inference (embeddings)
|   |---- variables.tf
|   |---- outputs.tf
|   |---- terraform.tfvars.example
|   |---- cloud-init-app.yaml             # App instance cloud-init (Docker, Caddy, compose)
|
|---- data/
|   |---- audio/
|   |   |---- doctor_patient_consultation.wav     # For Showcase 1
|   |---- documents/
|   |   |---- lab_report_sample.pdf               # For Showcase 2
|   |   |---- discharge_summary_sample.pdf
|   |   |---- radiology_report_sample.pdf
|   |---- knowledge_base/                         # For Showcase 3 + Lab
|   |   |---- diabetes_guidelines.md
|   |   |---- hypertension_guidelines.md
|   |   |---- drug_interactions.md
|   |   |---- cardiac_workup.md
|   |---- clinical_notes/                         # For Lab
|       |---- sample_note.txt
|
|---- 01_consultation_assistant/          Showcase 1: Doctor Assistant
|   |---- 01_consultation_assistant/
|   |   |---- main.py                             # FastAPI backend (SSE streaming)
|   |   |---- static/
|   |   |   |---- index.html                      # Clinical-editorial dark UI
|   |   |   |---- style.css
|   |   |   |---- app.js
|   |   |---- README.md
|   |---- 02_document_intelligence/
|   |   |---- main.py                             # FastAPI backend (OCR + RAG)
|   |   |---- static/
|   |   |   |---- index.html                      # Archival-modern parchment UI
|   |   |   |---- style.css
|   |   |   |---- app.js
|   |   |---- README.md
|   |---- 03_research_agent/
|       |---- main.py                             # FastAPI backend (agent + CoVe)
|       |---- static/
|       |   |---- index.html                      # Research-lab futuristic UI
|       |   |---- style.css
|       |   |---- app.js
|       |---- README.md
|
|---- notebooks/                                  # Interactive lab (students follow these)
|   |---- lab_00_setup.ipynb
|   |---- lab_01_clinical_understanding.ipynb
|   |---- lab_02_structured_extraction.ipynb
|   |---- lab_03_rag_knowledge_base.ipynb
|   |---- lab_04_agent.ipynb
|   |---- lab_05_safety.ipynb
|   |---- lab_06_full_pipeline.ipynb
|
|---- src/                                        # Shared Python modules
    |---- __init__.py
    |---- config.py                               # API clients, DB connection
    |---- models.py                               # JSON schemas for structured output
    |---- transcription.py                        # Voxtral STT (Showcase 1)
    |---- extraction.py                           # Structured extraction (Showcase 1 + Lab)
    |---- rag.py                                  # RAG pipeline (All showcases + Lab)
    |---- agent.py                                # Agent with tools (Showcase 3 + Lab)
    |---- ocr.py                                  # Pixtral OCR (Showcase 2)
    |---- verification.py                         # Chain-of-Verification (Showcase 3)
    |---- guardrails.py                           # Disclaimers, audit, validation (All)
```

---

## Medical AI Safety Architecture

Applied across showcases and lab - the key differentiator from generic AI demos:

| Layer | What | Where Used |
|---|---|---|
| 1. Grounded RAG + Citations | Every medical claim must cite a source document | All showcases + Lab 3-6 |
| 2. Structured Validation | Mistral native JSON schema mode enforces valid medical data | Showcase 1 + Lab 2 |
| 3. Human-in-the-Loop | Doctor approves before output is finalized | Showcase 3 + Lab 5 |
| 4. Chain-of-Verification | Each claim independently verified against knowledge base | Showcase 3 |
| 5. System Guardrails | Disclaimers, audit logging, refusal without evidence | All |

---

## Key Libraries

```
openai>=1.0                # Scaleway Generative APIs (OpenAI-compatible)
fastapi>=0.110             # Showcase backend (async, SSE)
uvicorn[standard]          # ASGI server
sse-starlette              # Server-Sent Events for FastAPI
pgvector>=0.3              # pgvector Python client
psycopg[binary]>=3.0       # PostgreSQL driver
python-dotenv              # Environment variables
pdf2image                  # PDF to images for Pixtral OCR (Showcase 2)
Pillow                     # Image processing
boto3                      # Scaleway Object Storage (S3-compatible)
jupyter                    # Lab notebooks
ipywidgets                 # Interactive notebook widgets
```

---

## Scaleway API Reference

- **Generative APIs base URL**: `https://api.scaleway.ai/v1`
- **Auth**: `Authorization: Bearer <SCW_SECRET_KEY>`
- **Chat**: `mistral-small-3.2-24b-instruct-2506` (24B, dense, EUR 0.15/0.35 per 1M tokens)
- **STT**: `voxtral-small-24b-2507`
- **Vision/OCR**: `pixtral-12b-2409`
- **Embeddings**: `bge-multilingual-gemma2`
- **Managed Inference**: `https://<deployment-uuid>.ifr.fr-par.scaleway.com/v1`
- **OpenTofu provider**: `scaleway/scaleway` v2.70+

---

## Workshop Timeline

| Time | Type | What |
|------|------|------|
| 0:00 | Presentation | AI in Healthcare - landscape, challenges, opportunity |
| 0:30 | **Showcase 1** | Doctor Assistant (Voxtral + structured extraction) |
| 0:50 | **Showcase 2** | Medical Document Intelligence (Pixtral OCR + RAG) |
| 1:10 | **Showcase 3** | Cross-domain Research Agent (multi-RAG + verification) |
| 1:30 | Presentation | Scaleway Cloud + AI Governance / EU AI Act |
| 1:50 | *Break* | |
| 2:00 | **Lab 0** | Setup - OpenTofu, env, first API call |
| 2:15 | **Lab 1** | Understanding clinical notes with Mistral |
| 2:30 | **Lab 2** | Structured data extraction |
| 2:50 | **Lab 3** | RAG with pgvector |
| 3:15 | **Lab 4** | Building a tool-calling agent |
| 3:40 | **Lab 5** | Safety guardrails & human review |
| 4:00 | **Lab 6** | Full pipeline + wrap-up discussion |
| 4:15 | Close | Q&A, next steps, tofu destroy |

---

## Implementation Steps (what we build)

### Phase 1: Scaffolding
- Repo structure, `.gitignore`, `requirements.txt`, `.env.example`
- OpenTofu: PostgreSQL + pgvector, Object Storage, Managed Inference (BGE embeddings on L4 for patient data privacy)

### Phase 2: Shared modules (`src/`)
- `config.py` - API clients, DB connection
- `models.py` - JSON schemas for structured output
- `rag.py` - Chunking, embedding, pgvector storage, retrieval with citations
- `extraction.py` - Structured extraction via Mistral JSON schema mode
- `guardrails.py` - Disclaimers, audit logging, citation enforcement
- `transcription.py` - Voxtral STT wrapper
- `ocr.py` - Pixtral OCR wrapper
- `agent.py` - Tool-calling agent loop
- `verification.py` - Chain-of-Verification

### Phase 3: Sample data
- Synthetic doctor-patient audio (WAV, ~5 min)
- Synthetic medical PDFs (lab report, discharge summary, radiology report)
- Medical knowledge base documents (4 markdown files: diabetes, hypertension, drug interactions, cardiac workup)
- Sample clinical note (the lab scenario text)

### Phase 4: Showcase apps
- `01_consultation_assistant/app.py` - Streamlit app for Showcase 1
- `02_document_intelligence/app.py` - Streamlit app for Showcase 2
- `03_research_agent/app.py` - Streamlit app for Showcase 3

### Phase 5: Lab notebooks
- 7 Jupyter notebooks (`lab_00` through `lab_06`)
- Mix of pre-written cells + `# TODO` cells for students
- Markdown explanations between cells

### Phase 6: Documentation
- `README.md` - Workshop overview, prerequisites, setup guide
- Individual READMEs for each showcase

---

## Cost Estimate

| Resource | Showcases (presenter) | Lab (per student) |
|---|---|---|
| Generative APIs | ~EUR 2-3 | ~EUR 0.50 (free tier: 1M tokens) |
| Managed Inference (BGE embeddings on L4) | ~EUR 4 (4h @ EUR 0.93/hr) | Not needed |
| PostgreSQL (DB-DEV-S) | ~EUR 0.10 | ~EUR 0.10 |
| Object Storage | ~EUR 0.01 | ~EUR 0.01 |
| **Total** | **~EUR 6-7** | **~EUR 0.60 per student** |
