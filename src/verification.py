"""
Chain-of-Verification (CoVe) pipeline.

Given an AI-generated response, this module:
1. Extracts individual factual claims.
2. Generates a verification question for each claim.
3. Searches the knowledge base for supporting evidence.
4. Labels each claim as VERIFIED / UNVERIFIED / NO_EVIDENCE.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable

from src.config import CHAT_MODEL, get_generative_client

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

_EXTRACT_CLAIMS_PROMPT = """\
You are a fact-checking assistant.  Given the following response, extract
every distinct factual medical claim as a JSON array of strings.

Return ONLY a JSON array — no surrounding text.

Response:
{response}
"""

_VERIFICATION_QUESTION_PROMPT = """\
For the following medical claim, generate a single concise search query
that could be used to verify it against a medical knowledge base.

Claim: {claim}

Return ONLY the search query — no explanation.
"""

_JUDGE_PROMPT = """\
You are a medical fact-checker.  Given a CLAIM and EVIDENCE retrieved from
a knowledge base, determine the verification status.

Claim: {claim}
Evidence: {evidence}

Respond with EXACTLY one JSON object:
{{"status": "VERIFIED" | "UNVERIFIED" | "NO_EVIDENCE", "explanation": "..."}}

- VERIFIED: the evidence clearly supports the claim.
- UNVERIFIED: the evidence contradicts the claim.
- NO_EVIDENCE: the evidence is insufficient to confirm or deny.
"""

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extract_claims(response: str) -> list[str]:
    """Use Mistral to split a response into individual factual claims."""
    client = get_generative_client()

    result = client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[
            {
                "role": "user",
                "content": _EXTRACT_CLAIMS_PROMPT.format(response=response),
            }
        ],
        temperature=0.0,
    )

    raw = result.choices[0].message.content.strip()
    # The model should return a JSON array; handle minor formatting issues.
    if not raw.startswith("["):
        start = raw.find("[")
        end = raw.rfind("]")
        if start != -1 and end != -1:
            raw = raw[start : end + 1]
    try:
        claims = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Failed to parse claims JSON, falling back to sentence split: %s", raw[:200])
        claims = [s.strip() for s in raw.split(".") if len(s.strip()) > 20]
    logger.info("Extracted %d claims", len(claims))
    return claims


def _make_query(claim: str) -> str:
    """Generate a verification search query for a single claim."""
    client = get_generative_client()

    result = client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[
            {
                "role": "user",
                "content": _VERIFICATION_QUESTION_PROMPT.format(claim=claim),
            }
        ],
        temperature=0.0,
        max_tokens=128,
    )

    return result.choices[0].message.content.strip()


def _judge(claim: str, evidence: str) -> dict:
    """Judge a claim against retrieved evidence."""
    client = get_generative_client()

    result = client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[
            {
                "role": "user",
                "content": _JUDGE_PROMPT.format(claim=claim, evidence=evidence),
            }
        ],
        temperature=0.0,
    )

    raw = result.choices[0].message.content.strip()
    # Tolerate markdown fences.
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Failed to parse judge JSON: %s", raw[:200])
        return {"status": "NO_EVIDENCE", "explanation": raw[:200]}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def verify_claims(
    response: str,
    search_fn: Callable[[str], list[dict]],
) -> list[dict]:
    """Run Chain-of-Verification on an AI-generated response.

    Parameters
    ----------
    response:
        The text whose claims should be verified.
    search_fn:
        A search function compatible with :func:`src.rag.search`.
        It receives a query string and returns a list of dicts,
        each containing at least ``content`` and ``source`` keys.

    Returns
    -------
    list[dict]
        One entry per claim::

            {
                "claim": str,
                "status": "VERIFIED" | "UNVERIFIED" | "NO_EVIDENCE",
                "evidence": str,
                "source": str | None,
            }
    """
    logger.info("verify_claims called, response_length=%d", len(response))
    claims = _extract_claims(response)
    if not claims:
        logger.warning("No claims extracted from response")
        return []
    results: list[dict] = []

    for i, claim in enumerate(claims):
        logger.info("Verifying claim %d/%d: %s", i + 1, len(claims), claim[:80])
        # Step 1: generate a targeted search query.
        query = _make_query(claim)

        # Step 2: search the knowledge base.
        hits = search_fn(query)

        if not hits:
            results.append(
                {
                    "claim": claim,
                    "status": "NO_EVIDENCE",
                    "evidence": "",
                    "source": None,
                }
            )
            continue

        # Combine top-k evidence for judging.
        combined_evidence = "\n\n".join(f"[{h.get('source', 'unknown')}]: {h['content']}" for h in hits[:3])
        top_source = hits[0].get("source")

        # Step 3: judge claim against evidence.
        judgement = _judge(claim, combined_evidence)

        results.append(
            {
                "claim": claim,
                "status": judgement.get("status", "NO_EVIDENCE"),
                "explanation": judgement.get("explanation", ""),
                "evidence": combined_evidence,
                "source": top_source,
            }
        )

    return results
