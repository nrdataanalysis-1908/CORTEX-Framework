import pytest

from evaluation.answer_quality import evaluate_annotations


def test_evaluate_annotations_aggregates_claim_and_abstention_labels():
    report = evaluate_annotations([
        {
            "id": "Q01",
            "answer_abstained": False,
            "abstention_expected": False,
            "claims": [
                {"claim": "Prazo de 15 minutos", "status": "supported", "evidence": "Trecho da política, linha 8"},
                {"claim": "Prazo de 10 minutos", "status": "contradicted", "evidence": "A política estabelece 15 minutos"},
                {"claim": "Atendimento 24 horas", "status": "unverifiable", "evidence": "Não há trecho sobre horário"},
            ],
        },
        {
            "id": "Q02",
            "answer_abstained": True,
            "abstention_expected": True,
            "claims": [],
        },
    ])

    assert report["cases"] == 2
    assert report["claims"] == 3
    assert report["claim_status_counts"] == {
        "contradicted": 1,
        "supported": 1,
        "unverifiable": 1,
        "unsupported": 0,
    }
    assert report["support_rate"] == pytest.approx(0.5)
    assert report["unsupported_claim_rate"] == pytest.approx(0.5)
    assert report["contradiction_rate"] == pytest.approx(0.5)
    assert report["abstention_accuracy"] == 1.0


def test_unverifiable_claims_are_excluded_from_decidable_denominator():
    report = evaluate_annotations([{
        "id": "Q01",
        "answer_abstained": False,
        "abstention_expected": False,
        "claims": [
            {"claim": "A", "status": "unverifiable", "evidence": "Sem evidência disponível"},
        ],
    }])
    assert report["decidable_claims"] == 0
    assert report["support_rate"] == 0.0
    assert report["unsupported_claim_rate"] == 0.0


def test_empty_dataset_returns_zero_metrics():
    report = evaluate_annotations([])
    assert report["cases"] == 0
    assert report["claims"] == 0
    assert report["abstention_accuracy"] == 0.0


@pytest.mark.parametrize("bad_case", [
    {"id": "", "answer_abstained": False, "abstention_expected": False, "claims": []},
    {"id": "Q", "answer_abstained": "false", "abstention_expected": False, "claims": []},
    {"id": "Q", "answer_abstained": False, "abstention_expected": False, "claims": "invalid"},
    {"id": "Q", "answer_abstained": False, "abstention_expected": False,
     "claims": [{"claim": "A", "status": "maybe", "evidence": "review"}]},
    {"id": "Q", "answer_abstained": False, "abstention_expected": False,
     "claims": [{"claim": "A", "status": "supported", "evidence": ""}]},
])
def test_invalid_annotations_are_rejected(bad_case):
    with pytest.raises(ValueError):
        evaluate_annotations([bad_case])


def test_duplicate_case_ids_are_rejected():
    case = {
        "id": "Q01",
        "answer_abstained": False,
        "abstention_expected": False,
        "claims": [],
    }
    with pytest.raises(ValueError, match="Duplicate"):
        evaluate_annotations([case, case])
