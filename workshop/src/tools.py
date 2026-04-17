"""The five agent tools for the ReAct drug interaction agent.

Tools:
    search_drug_kb      - Embedding search across all label-section chunks
    lookup_interactions - Targeted retrieval of drug_interactions chunks
    lookup_population_warnings - Targeted retrieval of population-specific chunks
    flag_severity       - Classify and re-order findings by severity
    summarize_evidence  - Synthesise the final report with source attribution
"""

from __future__ import annotations

import json
import logging
from typing import Any

from workshop.src.rag import similarity_search

logger = logging.getLogger(__name__)

# Severity levels in order from most to least severe
SEVERITY_ORDER = {"CRITICAL": 0, "MAJOR": 1, "MODERATE": 2, "MINOR": 3}

# Population -> section type mapping
POPULATION_SECTION_MAP = {
    "pregnancy": "pregnancy",
    "pediatric": "pediatric_use",
    "geriatric": "geriatric_use",
}

# Keywords for renal/hepatic filtering on use_in_specific_populations
POPULATION_KEYWORDS = {
    "renal": ["renal", "kidney", "creatinine clearance", "egfr", "nephro"],
    "hepatic": ["hepatic", "liver", "child-pugh", "hepato", "cirrhosis"],
}


class ToolKit:
    """Collection of the five agent tools.

    Args:
        conn: A psycopg connection to the pgvector database.
        embeddings_client: An EmbeddingsClient for generating query embeddings.
        llm_client: An OpenAI-compatible chat client (Mistral Small 3.2).
    """

    def __init__(self, conn: Any, embeddings_client: Any, llm_client: Any) -> None:
        self._conn = conn
        self._embeddings = embeddings_client
        self._llm = llm_client

    # -----------------------------------------------------------------
    # Tool 1: search_drug_kb
    # -----------------------------------------------------------------

    def search_drug_kb(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """Embedding search across all label-section chunks.

        The 'I am not sure exactly which drug or section to look in' tool.

        Args:
            query: Free-text search query.
            top_k: Number of results to return.

        Returns:
            Top-K chunks with drug_name, section_type, set_id, text.
        """
        query_embedding = self._embeddings.embed(query)
        results = similarity_search(self._conn, query_embedding, k=top_k)
        return results

    # -----------------------------------------------------------------
    # Tool 2: lookup_interactions
    # -----------------------------------------------------------------

    def lookup_interactions(self, drug_name: str) -> list[dict[str, Any]]:
        """Targeted retrieval of drug_interactions chunks for a specific drug.

        The agent calls this once per drug in the input list.

        Args:
            drug_name: Generic drug name to look up.

        Returns:
            List of drug_interactions chunks with full text and set_id citation.
            Empty list if the drug is not found.
        """
        query_embedding = self._embeddings.embed(f"{drug_name} drug interactions")
        results = similarity_search(
            self._conn,
            query_embedding,
            k=5,
            filters={
                "drug_name": drug_name,
                "section_type": "drug_interactions",
            },
        )
        return results

    # -----------------------------------------------------------------
    # Tool 3: lookup_population_warnings
    # -----------------------------------------------------------------

    def lookup_population_warnings(self, drug_name: str, population: str) -> list[dict[str, Any]]:
        """Targeted retrieval of population-specific chunks for a drug.

        Args:
            drug_name: Generic drug name to look up.
            population: One of 'pregnancy', 'pediatric', 'geriatric',
                'renal', 'hepatic'.

        Returns:
            List of matching chunks with set_id citation.
        """
        # Direct section mapping for pregnancy/pediatric/geriatric
        if population in POPULATION_SECTION_MAP:
            section_type = POPULATION_SECTION_MAP[population]
            query_embedding = self._embeddings.embed(f"{drug_name} {population}")
            results = similarity_search(
                self._conn,
                query_embedding,
                k=5,
                filters={
                    "drug_name": drug_name,
                    "section_type": section_type,
                },
            )
            return results

        # For renal/hepatic, search use_in_specific_populations and filter by keyword
        if population in POPULATION_KEYWORDS:
            keywords = POPULATION_KEYWORDS[population]
            query_embedding = self._embeddings.embed(f"{drug_name} {population} impairment")
            results = similarity_search(
                self._conn,
                query_embedding,
                k=10,
                filters={
                    "drug_name": drug_name,
                    "section_type": "use_in_specific_populations",
                },
            )
            # Filter results by keyword presence in text
            filtered = []
            for row in results:
                text_lower = row.get("text", "").lower()
                if any(kw in text_lower for kw in keywords):
                    filtered.append(row)
            return filtered

        logger.warning("Unknown population '%s'", population)
        return []

    # -----------------------------------------------------------------
    # Tool 4: flag_severity
    # -----------------------------------------------------------------

    def flag_severity(self, findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Classify and re-order findings by severity.

        CRITICAL is automatically assigned to any finding sourced from a
        boxed_warning chunk. The rest is classified by Mistral Small 3.2.

        Args:
            findings: List of finding dicts with 'claim', 'source_section_type',
                'source_id', 'evidence_snippet'.

        Returns:
            Same findings with 'severity' added, sorted CRITICAL -> MINOR.
        """
        classified = []

        for finding in findings:
            finding_copy = dict(finding)

            if finding.get("source_section_type") == "boxed_warning":
                finding_copy["severity"] = "CRITICAL"
            else:
                # Ask LLM to classify severity
                severity = self._classify_severity_via_llm(finding)
                finding_copy["severity"] = severity

            classified.append(finding_copy)

        # Sort by severity order
        classified.sort(key=lambda f: SEVERITY_ORDER.get(f.get("severity", "MINOR"), 3))

        return classified

    def _classify_severity_via_llm(self, finding: dict[str, Any]) -> str:
        """Use the LLM to classify a finding's severity.

        Args:
            finding: A finding dict.

        Returns:
            One of 'CRITICAL', 'MAJOR', 'MODERATE', 'MINOR'.
        """
        prompt = (
            "Classify the severity of this drug interaction or population warning finding. "
            "Respond with exactly one word: CRITICAL, MAJOR, MODERATE, or MINOR.\n\n"
            f"Claim: {finding.get('claim', '')}\n"
            f"Evidence: {finding.get('evidence_snippet', '')}"
        )

        response = self._llm.chat.completions.create(
            model="mistral-small-3.2-24b-instruct-2506",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=10,
            temperature=0.0,
        )

        severity = response.choices[0].message.content.strip().upper()

        # Validate
        if severity not in SEVERITY_ORDER:
            logger.warning("LLM returned unexpected severity '%s', defaulting to MODERATE", severity)
            severity = "MODERATE"

        return severity

    # -----------------------------------------------------------------
    # Tool 5: summarize_evidence
    # -----------------------------------------------------------------

    def summarize_evidence(self, findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Synthesise the final report preserving source attribution.

        Args:
            findings: List of severity-flagged findings.

        Returns:
            Structured JSON: severity-first ordered list of claims, each
            with source_id and evidence_snippet.
        """
        findings_text = json.dumps(findings, indent=2)

        prompt = (
            "Synthesize the following drug interaction and population warning findings "
            "into a final report. Return a JSON array where each element has:\n"
            '- "claim": the finding statement\n'
            '- "source_id": in the format "<drug_name> :: <section_type> :: <set_id>"\n'
            '- "evidence_snippet": the exact label text supporting the claim\n\n'
            "Preserve the severity ordering (CRITICAL first, then MAJOR, MODERATE, MINOR). "
            "Return ONLY the JSON array, no other text.\n\n"
            f"Findings:\n{findings_text}"
        )

        response = self._llm.chat.completions.create(
            model="mistral-small-3.2-24b-instruct-2506",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
        )

        content = response.choices[0].message.content.strip()

        # Parse the JSON response
        try:
            result = json.loads(content)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code blocks
            if "```" in content:
                json_str = content.split("```")[1]
                if json_str.startswith("json"):
                    json_str = json_str[4:]
                result = json.loads(json_str.strip())
            else:
                logger.error("Failed to parse LLM response as JSON: %s", content[:200])
                # Fall back to returning findings as-is
                result = [
                    {
                        "claim": f.get("claim", ""),
                        "source_id": f.get("source_id", ""),
                        "evidence_snippet": f.get("evidence_snippet", ""),
                    }
                    for f in findings
                ]

        return result


# ---------------------------------------------------------------------------
# Tool definitions for the Mistral tool-calling API
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "search_drug_kb",
            "description": (
                "Embedding search across all drug label section chunks. "
                "Use when you are not sure which drug or section to look in."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Free-text search query about drug interactions, warnings, or effects.",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of results to return (default 5).",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_interactions",
            "description": (
                "Retrieve drug_interactions chunks for a specific drug. Call this once per drug in the medication list."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "drug_name": {
                        "type": "string",
                        "description": "Generic drug name to look up interactions for.",
                    },
                },
                "required": ["drug_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_population_warnings",
            "description": (
                "Retrieve population-specific warnings (pregnancy, pediatric, geriatric, "
                "renal, hepatic) for a specific drug."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "drug_name": {
                        "type": "string",
                        "description": "Generic drug name.",
                    },
                    "population": {
                        "type": "string",
                        "enum": ["pregnancy", "pediatric", "geriatric", "renal", "hepatic"],
                        "description": "The patient population to check warnings for.",
                    },
                },
                "required": ["drug_name", "population"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "flag_severity",
            "description": (
                "Classify and re-order a list of findings by severity "
                "(CRITICAL > MAJOR > MODERATE > MINOR). "
                "Any finding from a boxed_warning is forced to CRITICAL."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "findings": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "claim": {"type": "string"},
                                "source_section_type": {"type": "string"},
                                "source_id": {"type": "string"},
                                "evidence_snippet": {"type": "string"},
                            },
                        },
                        "description": "List of findings to classify.",
                    },
                },
                "required": ["findings"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "summarize_evidence",
            "description": (
                "Synthesize the final report from severity-flagged findings, "
                "preserving source attribution with claim/source_id/evidence_snippet triples."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "findings": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "claim": {"type": "string"},
                                "source_id": {"type": "string"},
                                "evidence_snippet": {"type": "string"},
                                "severity": {"type": "string"},
                                "source_section_type": {"type": "string"},
                            },
                        },
                        "description": "List of severity-flagged findings to summarize.",
                    },
                },
                "required": ["findings"],
            },
        },
    },
]
