"""Label section chunker for openFDA drug labels.

Splits each trimmed openFDA label into one chunk per SPL section, carrying
mandatory metadata columns for pgvector storage and grounded citations.

The drug_interactions_table section is folded into the drug_interactions chunk
text (not stored separately) to keep interaction data unified.

Adapted from workshop/src/chunker.py for the Drug Interactions showcase.
"""

from __future__ import annotations

from typing import Any

# Sections that produce individual chunks
CHUNKABLE_SECTIONS: list[str] = [
    "boxed_warning",
    "indications_and_usage",
    "contraindications",
    "warnings_and_cautions",
    "drug_interactions",
    "adverse_reactions",
    "use_in_specific_populations",
    "pregnancy",
    "pediatric_use",
    "geriatric_use",
    "mechanism_of_action",
    "clinical_pharmacology",
]

OPENFDA_LABEL_BASE_URL = "https://api.fda.gov/drug/label.json?search="


def _build_source_url(set_id: str, application_number: str) -> str:
    """Build a working openFDA label URL.

    The 199-/200-label snapshot rarely populates `openfda.set_id` (post-2025
    openFDA records often only carry `application_number`). Pick the field
    that's actually populated so the citation link resolves to a real label.
    """
    if set_id:
        return f"{OPENFDA_LABEL_BASE_URL}openfda.set_id:{set_id}"
    if application_number:
        return f"{OPENFDA_LABEL_BASE_URL}openfda.application_number:{application_number}"
    return ""


def _extract_text(section_value: Any) -> str:
    """Extract text from an openFDA section value.

    openFDA sections are typically lists of strings. This joins them with
    newlines to produce a single text block.
    """
    if isinstance(section_value, list):
        return "\n".join(str(item) for item in section_value)
    return str(section_value)


def _extract_metadata(label: dict[str, Any]) -> dict[str, str]:
    """Extract metadata fields from the openfda block of a label."""
    openfda = label.get("openfda", {})

    def _first(field: str) -> str:
        """Get the first element of a list field, or empty string."""
        val = openfda.get(field, [""])
        if isinstance(val, list):
            return val[0] if val else ""
        return str(val)

    set_id = _first("set_id")
    application_number = _first("application_number")

    return {
        "drug_name": _first("generic_name"),
        "generic_name": _first("generic_name"),
        "brand_name": _first("brand_name"),
        "set_id": set_id,
        "application_number": application_number,
        "manufacturer_name": _first("manufacturer_name"),
        "source_url": _build_source_url(set_id, application_number),
    }


def chunk_label(label: dict[str, Any]) -> list[dict[str, Any]]:
    """Split a trimmed openFDA label into section-typed chunks.

    Args:
        label: A single trimmed label record as returned by fetch_labels().

    Returns:
        List of chunk dicts, each with: section_type, text, drug_name,
        generic_name, brand_name, set_id, application_number,
        manufacturer_name, source_url.
    """
    metadata = _extract_metadata(label)
    chunks: list[dict[str, Any]] = []

    for section_type in CHUNKABLE_SECTIONS:
        if section_type not in label:
            continue

        text = _extract_text(label[section_type])

        # Fold drug_interactions_table into drug_interactions chunk
        if section_type == "drug_interactions" and "drug_interactions_table" in label:
            table_text = _extract_text(label["drug_interactions_table"])
            text = f"{text}\n\n--- Drug Interactions Table ---\n{table_text}"

        chunk = {
            "section_type": section_type,
            "text": text,
            **metadata,
        }
        chunks.append(chunk)

    return chunks
