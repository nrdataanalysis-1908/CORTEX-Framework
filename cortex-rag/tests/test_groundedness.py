import pytest

from evaluation.groundedness import validate_groundedness_result


EVIDENCE = {"E1", "E2"}


def _claim(status="supported", evidence_ids=None):
    return {
        "claim": "O prazo é de 15 minutos.",
        "status": status,
        "evidence_ids": ["E1"] if evidence_ids is None else evidence_ids,
        "rationale": "O trecho E1 declara explicitamente o prazo.",
    }


def test_all_supported_claims_are_grounded():
    result = validate_groundedness_result(
        {"claims": [_claim(), _claim(evidence_ids=["E2"])]}, EVIDENCE
    )
    assert result["status"] == "grounded"
    assert result["claim_count"] == 2
    assert result["claim_status_counts"]["supported"] == 2


@pytest.mark.parametrize(
    ("statuses", "expected"),
    [
        (["supported", "unsupported"], "unsupported"),
        (["supported", "contradicted"], "contradicted"),
        (["supported", "unverifiable"], "inconclusive"),
    ],
)
def test_aggregate_status_preserves_worst_claim_outcome(statuses, expected):
    result = validate_groundedness_result(
        {"claims": [_claim(status) for status in statuses]}, EVIDENCE
    )
    assert result["status"] == expected


def test_empty_claim_list_is_not_evaluated():
    result = validate_groundedness_result({"claims": []}, EVIDENCE)
    assert result["status"] == "not_evaluated"
    assert result["claim_count"] == 0


@pytest.mark.parametrize(
    "payload",
    [
        {"claims": [{"claim": "x", "status": "supported", "evidence_ids": ["E99"], "rationale": "x"}]},
        {"claims": [{"claim": "x", "status": "supported", "evidence_ids": [], "rationale": "x"}]},
        {"claims": [{"claim": "x", "status": "unknown", "evidence_ids": ["E1"], "rationale": "x"}]},
        {"claims": [{"claim": "x", "status": "supported", "evidence_ids": ["E1"], "rationale": ""}]},
        {"claims": "invalid"},
    ],
)
def test_invalid_judge_output_is_rejected(payload):
    with pytest.raises(ValueError):
        validate_groundedness_result(payload, EVIDENCE)
