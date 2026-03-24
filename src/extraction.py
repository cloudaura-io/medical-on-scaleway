"""
Structured clinical-note extraction from free-text transcripts.

Uses Mistral with JSON schema enforcement so the output always
conforms to ClinicalNote.
"""

from __future__ import annotations

import json

from src.config import get_generative_client, CHAT_MODEL
from src.models import CLINICAL_NOTE_SCHEMA

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are a medical scribe AI.  Given a transcript of a doctor-patient
encounter, extract a structured clinical note.

Rules:
- Use ONLY information explicitly stated in the transcript.
- If a field is not mentioned, use null (for scalars) or an empty list/object.
- Medication names should use generic names where possible.
- Vital signs should include units (e.g., "120/80 mmHg").
- The assessment should be a concise clinical impression.
- Plan items should be actionable and ordered by priority.
- Do NOT hallucinate or infer diagnoses beyond what the clinician states.
"""

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_clinical_note(transcript: str) -> dict:
    """Extract a structured clinical note from a consultation transcript.

    Parameters
    ----------
    transcript:
        Free-text transcript of a doctor-patient encounter.

    Returns
    -------
    dict
        Parsed JSON matching the ClinicalNote schema.
    """
    client = get_generative_client()

    response = client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": transcript},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": CLINICAL_NOTE_SCHEMA,
        },
        temperature=0.1,
    )

    raw = response.choices[0].message.content
    return json.loads(raw)
