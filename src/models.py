"""
JSON schemas for Mistral structured output.

These are plain Python dicts intended for use with:
    response_format={"type": "json_schema", "json_schema": {"name": ..., "schema": ...}}

No Pydantic — keeps dependencies light and matches the Mistral API directly.
"""

# ---------------------------------------------------------------------------
# ClinicalNote — structured extraction from a doctor-patient transcript
# ---------------------------------------------------------------------------

CLINICAL_NOTE_SCHEMA = {
    "name": "ClinicalNote",
    "schema": {
        "type": "object",
        "properties": {
            "patient_name": {
                "type": "string",
                "description": "Full name of the patient.",
            },
            "age": {
                "type": ["integer", "null"],
                "description": "Patient age in years, or null if not mentioned.",
            },
            "sex": {
                "type": ["string", "null"],
                "enum": ["male", "female", "other", None],
                "description": "Biological sex or null if not mentioned.",
            },
            "chief_complaint": {
                "type": "string",
                "description": "Primary reason for the visit in the patient's own words.",
            },
            "symptoms": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of reported symptoms.",
            },
            "medications": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Current medications mentioned during the encounter.",
            },
            "vitals": {
                "type": "object",
                "properties": {
                    "blood_pressure": {"type": ["string", "null"]},
                    "heart_rate": {"type": ["integer", "null"]},
                    "temperature": {"type": ["number", "null"]},
                    "respiratory_rate": {"type": ["integer", "null"]},
                    "oxygen_saturation": {"type": ["number", "null"]},
                },
                "description": "Vital signs recorded during the visit.",
                "additionalProperties": True,
            },
            "assessment": {
                "type": "string",
                "description": "Clinician's assessment / working diagnosis.",
            },
            "plan": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Ordered list of next steps / treatment plan items.",
            },
        },
        "required": [
            "patient_name",
            "chief_complaint",
            "symptoms",
            "medications",
            "vitals",
            "assessment",
            "plan",
        ],
        "additionalProperties": False,
    },
}

# ---------------------------------------------------------------------------
# DrugInteraction — pairwise interaction check
# ---------------------------------------------------------------------------

DRUG_INTERACTION_SCHEMA = {
    "name": "DrugInteraction",
    "schema": {
        "type": "object",
        "properties": {
            "drug1": {
                "type": "string",
                "description": "First drug name (generic).",
            },
            "drug2": {
                "type": "string",
                "description": "Second drug name (generic).",
            },
            "severity": {
                "type": "string",
                "enum": ["none", "minor", "moderate", "major", "contraindicated"],
                "description": "Interaction severity level.",
            },
            "description": {
                "type": "string",
                "description": "Plain-language explanation of the interaction.",
            },
            "recommendation": {
                "type": "string",
                "description": "Clinical recommendation (e.g., dose adjustment, monitoring).",
            },
        },
        "required": ["drug1", "drug2", "severity", "description", "recommendation"],
        "additionalProperties": False,
    },
}

# ---------------------------------------------------------------------------
# ResearchFinding — a single claim extracted from AI-generated text
# ---------------------------------------------------------------------------

RESEARCH_FINDING_SCHEMA = {
    "name": "ResearchFinding",
    "schema": {
        "type": "object",
        "properties": {
            "claim": {
                "type": "string",
                "description": "A factual medical claim extracted from the response.",
            },
            "evidence": {
                "type": "string",
                "description": "Supporting evidence found in the knowledge base.",
            },
            "source": {
                "type": ["string", "null"],
                "description": "Source document or reference for the evidence.",
            },
            "verification_status": {
                "type": "string",
                "enum": ["VERIFIED", "UNVERIFIED", "NO_EVIDENCE"],
                "description": "Whether the claim could be confirmed against the knowledge base.",
            },
        },
        "required": ["claim", "evidence", "source", "verification_status"],
        "additionalProperties": False,
    },
}
