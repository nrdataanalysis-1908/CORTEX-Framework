"""Claim-level groundedness evaluation and strict judge-output validation.

The LLM judge is a fallible evaluator, not a factuality oracle. Its verdicts
are therefore reported separately from retrieval and citation provenance.
"""
from __future__ import annotations

import json
from typing import Any

CLAIM_VERDICTS = {"supported", "unsupported", "contradicted", "unverifiable"}
AGGREGATE_STATUSES = {
    "grounded",
    "partially_grounded",
    "not_grounded",
    "contradicted",
    "unverifiable",
    "invalid_citation_reference",
    "evaluation_error",
}


class GroundednessEvaluationError(ValueError):
    """Raised when the judge response cannot be safely interpreted."""


def parse_judge_output(raw: str, evidence_ids: set[str]) -> dict[str, Any]:
    """Parse and validate claim-level judge output against supplied evidence IDs."""
    try:
        payload = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as exc:
        raise GroundednessEvaluationError("Judge returned invalid JSON.") from exc

    if not isinstance(payload, dict) or not isinstance(payload.get("claims"), list):
        raise GroundednessEvaluationError("Judge output must contain a claims list.")

    claims: list[dict[str, Any]] = []
    for index, item in enumerate(payload["claims"]):
        if not isinstance(item, dict):
            raise GroundednessEvaluationError(f"Claim {index} must be an object.")
        claim = item.get("claim")
        verdict = item.get("verdict")
        rationale = item.get("rationale")
        citation_ids = item.get("citation_ids")

        if not isinstance(claim, str) or not claim.strip():
            raise GroundednessEvaluationError(f"Claim {index} requires claim text.")
        if verdict not in CLAIM_VERDICTS:
            raise GroundednessEvaluationError(f"Claim {index} has an invalid verdict.")
        if not isinstance(rationale, str) or not rationale.strip():
            raise GroundednessEvaluationError(f"Claim {index} requires a rationale.")
        if (
            not isinstance(citation_ids, list)
            or any(not isinstance(value, str) for value in citation_ids)
        ):
            raise GroundednessEvaluationError(f"Claim {index} citation_ids must be a string list.")

        citation_ids = list(dict.fromkeys(citation_ids))
        invalid_ids = [value for value in citation_ids if value not in evidence_ids]
        effective_verdict = "invalid_citation_reference" if invalid_ids else verdict
        claims.append({
            "claim": claim.strip(),
            "verdict": effective_verdict,
            "citation_ids": [value for value in citation_ids if value in evidence_ids],
            "unresolved_citation_ids": invalid_ids,
            "rationale": rationale.strip(),
        })

    verdicts = [item["verdict"] for item in claims]
    if not claims or all(value == "unverifiable" for value in verdicts):
        status = "unverifiable"
    elif "invalid_citation_reference" in verdicts:
        status = "invalid_citation_reference"
    elif "contradicted" in verdicts:
        status = "contradicted"
    elif "unsupported" in verdicts:
        status = "partially_grounded" if "supported" in verdicts else "not_grounded"
    elif all(value == "supported" for value in verdicts):
        status = "grounded"
    else:
        status = "unverifiable"

    return {
        "groundedness": status,
        "groundedness_claims": claims,
        "groundedness_summary": {
            "total": len(claims),
            "supported": verdicts.count("supported"),
            "unsupported": verdicts.count("unsupported"),
            "contradicted": verdicts.count("contradicted"),
            "unverifiable": verdicts.count("unverifiable"),
            "invalid_citation_reference": verdicts.count("invalid_citation_reference"),
        },
    }
