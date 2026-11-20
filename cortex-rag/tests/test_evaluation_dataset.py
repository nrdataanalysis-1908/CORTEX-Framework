import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "evaluation" / "fixtures" / "manual_operacional_sintetico.txt"
QUESTIONS = ROOT / "evaluation" / "questions.json"


def test_evaluation_dataset_has_twenty_unique_cases():
    cases = json.loads(QUESTIONS.read_text(encoding="utf-8"))
    assert len(cases) == 20
    assert len({case["id"] for case in cases}) == 20


def test_every_gold_evidence_exists_in_synthetic_fixture():
    fixture = FIXTURE.read_text(encoding="utf-8").casefold()
    cases = json.loads(QUESTIONS.read_text(encoding="utf-8"))
    for case in cases:
        assert case["expected_evidence"].casefold() in fixture, case["id"]
        assert case["expected_facts"], case["id"]
