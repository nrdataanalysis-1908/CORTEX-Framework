"""Human-annotation metrics for answer support and abstention quality.

This module never judges answer text. It aggregates labels assigned by reviewers
against the retrieved evidence and the gold reference.
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

CLAIM_STATUSES = {"supported", "unsupported", "contradicted", "unverifiable"}


def evaluate_annotations(cases: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate reviewer labels without inferring factuality from answer text."""
    case_list = list(cases)
    seen_ids: set[str] = set()
    counts = {status: 0 for status in sorted(CLAIM_STATUSES)}
    abstention_correct = 0

    for case in case_list:
        if not isinstance(case, dict):
            raise ValueError("Each annotation case must be an object.")

        case_id = case.get("id")
        if not isinstance(case_id, str) or not case_id.strip():
            raise ValueError("Each case requires a non-empty string id.")
        if case_id in seen_ids:
            raise ValueError(f"Duplicate annotation case id: {case_id}")
        seen_ids.add(case_id)

        for field in ("answer_abstained", "abstention_expected"):
            if not isinstance(case.get(field), bool):
                raise ValueError(f"{case_id}: {field} must be boolean.")

        if case["answer_abstained"] == case["abstention_expected"]:
            abstention_correct += 1

        claims = case.get("claims")
        if not isinstance(claims, list):
            raise ValueError(f"{case_id}: claims must be a list.")

        for index, claim in enumerate(claims):
            if not isinstance(claim, dict):
                raise ValueError(f"{case_id}: claim {index} must be an object.")
            text = claim.get("claim")
            status = claim.get("status")
            evidence = claim.get("evidence")
            if not isinstance(text, str) or not text.strip():
                raise ValueError(f"{case_id}: claim {index} requires claim text.")
            if status not in CLAIM_STATUSES:
                raise ValueError(
                    f"{case_id}: claim {index} status must be one of "
                    f"{', '.join(sorted(CLAIM_STATUSES))}."
                )
            if not isinstance(evidence, str) or not evidence.strip():
                raise ValueError(f"{case_id}: claim {index} requires reviewer evidence or rationale.")
            counts[status] += 1

    total_claims = sum(counts.values())
    decidable_claims = total_claims - counts["unverifiable"]
    supported = counts["supported"]
    unsupported_or_contradicted = counts["unsupported"] + counts["contradicted"]

    return {
        "cases": len(case_list),
        "claims": total_claims,
        "claim_status_counts": counts,
        "decidable_claims": decidable_claims,
        "support_rate": supported / decidable_claims if decidable_claims else 0.0,
        "unsupported_claim_rate": (
            unsupported_or_contradicted / decidable_claims
            if decidable_claims else 0.0
        ),
        "contradiction_rate": (
            counts["contradicted"] / decidable_claims if decidable_claims else 0.0
        ),
        "abstention_accuracy": (
            abstention_correct / len(case_list) if case_list else 0.0
        ),
        "abstention_correct": abstention_correct,
        "interpretation": (
            "Metrics aggregate human reviewer labels. Unverifiable claims are "
            "excluded from claim-rate denominators and reported separately. "
            "These metrics are not an automated factuality or groundedness judge."
        ),
    }
