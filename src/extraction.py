"""
Structured clinical-note extraction from free-text transcripts.

Uses Mistral with JSON schema enforcement so the output always
conforms to ClinicalNote.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator

from src.config import CHAT_MODEL, get_generative_client
from src.logging_config import timed_operation
from src.models import CLINICAL_NOTE_SCHEMA

logger = logging.getLogger(__name__)

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


@timed_operation
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
    logger.info(
        "extract_clinical_note called, transcript_length=%d",
        len(transcript),
    )
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


def extract_clinical_note_stream(transcript: str) -> Iterator[tuple[str, object]]:
    """Yield events as Mistral streams the clinical-note JSON.

    Yields tuples of (event_type, payload):
        - ("token", str) for each raw text chunk as the model emits it.
        - ("clinical_note", dict) with the parsed JSON once the stream finishes
          and the accumulated output parses cleanly.
        - ("error", str) if the accumulated output fails to parse.
    """
    logger.info("extract_clinical_note_stream called, transcript_length=%d", len(transcript))
    client = get_generative_client()

    stream = client.chat.completions.create(
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
        stream=True,
    )

    chunks: list[str] = []
    for event in stream:
        if not event.choices:
            continue
        delta = getattr(event.choices[0], "delta", None)
        text = getattr(delta, "content", None) if delta else None
        if text:
            chunks.append(text)
            yield ("token", text)

    raw = "".join(chunks)
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.error("Failed to parse streamed clinical note JSON: %s", exc)
        yield ("error", f"JSON parse failed: {exc}")
        return

    yield ("clinical_note", parsed)
