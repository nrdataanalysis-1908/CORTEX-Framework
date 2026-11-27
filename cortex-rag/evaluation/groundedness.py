"""Claim-level groundedness evaluation against retrieved RAG evidence.

The evaluator is an LLM-assisted judge, not a proof system. Its output is
validated against the evidence IDs supplied to the judge and remains auditable.
"""
from __future__ import annotations

from collections import Counter
from typing import Any

CLAIM_STATUSES = {"supported", "unsupported", "contradicted", "unverifiable"}


def validate_groundedness_result(
    payload: dict[str, Any], evidence_ids: set[str]
) -> dict[str, Any]:
    """Validate judge output and derive an aggregate groundedness status."""
    if not isinstance(payload, dict) or not isinstance(payload.get("claims"), list):
        raise ValueError("Groundedness result must contain a claims list.")

    claims: list[dict[str, Any]] = []
    for index, item in enumerate(payload["claims"]):
        if not isinstance(item, dict):
            raise ValueError(f"Claim {index} must be an object.")
        claim = item.get("claim")
        status = item.get("status")
        cited = item.get("evidence_ids")
        rationale = item.get("rationale")
        if not isinstance(claim, str) or not claim.strip():
            raise ValueError(f"Claim {index} requires non-empty text.")
        if status not in CLAIM_STATUSES:
            raise ValueError(f"Claim {index} has an invalid status.")
        if not isinstance(cited, list) or any(
            not isinstance(value, str) for value in cited
        ):
            raise ValueError(f"Claim {index} evidence_ids must be a string list.")
        if len(cited) != len(set(cited)):
            raise ValueError(f"Claim {index} contains duplicate evidence IDs.")
        unknown = sorted(set(cited) - evidence_ids)
        if unknown:
            raise ValueError(
                f"Claim {index} references evidence not supplied: {', '.join(unknown)}"
            )
        if not isinstance(rationale, str) or not rationale.strip():
            raise ValueError(f"Claim {index} requires a rationale.")
        if status == "supported" and not cited:
            raise ValueError(f"Claim {index} cannot be supported without evidence.")
        claims.append({
            "claim": claim.strip(),
            "status": status,
            "evidence_ids": cited,
            "rationale": rationale.strip(),
        })

    counts = dict(Counter(item["status"] for item in claims))
    for status in sorted(CLAIM_STATUSES):
        counts.setdefault(status, 0)

    if not claims:
        overall = "not_evaluated"
    elif counts["contradicted"]:
        overall = "contradicted"
    elif counts["unsupported"]:
        overall = "unsupported"
    elif counts["unverifiable"]:
        overall = "inconclusive"
    else:
        overall = "grounded"

    return {
        "status": overall,
        "claims": claims,
        "claim_count": len(claims),
        "claim_status_counts": counts,
        "evaluation_method": "llm_judge",
        "disclaimer": (
            "LLM-judge assessment is an estimate, not a factuality guarantee; "
            "validate with human review for high-impact use."
        ),
    }
