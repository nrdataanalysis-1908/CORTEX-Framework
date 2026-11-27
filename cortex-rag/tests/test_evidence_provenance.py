from types import SimpleNamespace
import json

import pytest

from app import rag


class FakeConnection:
    def __init__(self, rows):
        self.rows = rows
        self.query = None
        self.params = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, query, params):
        self.query = query
        self.params = params
        return self

    def fetchall(self):
        return self.rows


def _completion(answer):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=answer))]
    )


def _mock_model(operation, call, answer):
    if operation == "chat.completions.groundedness":
        return _completion(json.dumps({
            "claims": [{
                "claim": "O prazo é de 15 dias.",
                "status": "supported",
                "evidence_ids": ["E99"] if "[E99]" in answer else ["E1"],
                "rationale": "O trecho indicado informa o prazo de 15 dias.",
            }]
        }))
    return _completion(answer)


@pytest.fixture
def retrieval(monkeypatch):
    rows = [
        (17, 91, "manual.pdf", 2, "O prazo operacional é de 15 dias.", 0.91),
        (17, 92, "manual.pdf", 3, "A solicitação deve ser protocolada.", 0.82),
    ]
    connection = FakeConnection(rows)
    monkeypatch.setattr(rag, "embed", lambda texts: [[0.1, 0.2]])
    monkeypatch.setattr(rag, "connect", lambda: connection)
    return connection


def test_answer_returns_verifiable_document_and_chunk_references(retrieval, monkeypatch):
    monkeypatch.setattr(
        rag,
        "_call_openai",
        lambda operation, call: _mock_model(operation, call, "O prazo é de 15 dias [E1]."),
    )

    result = rag.answer_question("Qual é o prazo?")

    assert "c.id" in retrieval.query
    assert "d.id" in retrieval.query
    assert result["evidence_retrieved"] is True
    assert result["evidence_status"] == "retrieved_cited_not_verified"
    assert result["groundedness"] == "grounded"
    assert result["citation_ids"] == ["E1"]
    assert result["unresolved_citation_ids"] == []
    assert result["evidence"][0] == {
        "evidence_id": "E1",
        "document_id": 17,
        "chunk_id": 91,
        "filename": "manual.pdf",
        "chunk_index": 2,
        "similarity": 0.91,
        "text": "O prazo operacional é de 15 dias.",
    }


def test_answer_flags_unknown_citation_ids(retrieval, monkeypatch):
    monkeypatch.setattr(
        rag,
        "_call_openai",
        lambda operation, call: _mock_model(operation, call, "O prazo é de 15 dias [E99]."),
    )

    result = rag.answer_question("Qual é o prazo?")

    assert result["citation_ids"] == []
    assert result["unresolved_citation_ids"] == ["E99"]
    assert result["evidence_status"] == "invalid_citation_reference"
    assert result["groundedness"] == "evaluation_error"


def test_answer_reports_retrieved_but_uncited_evidence(retrieval, monkeypatch):
    monkeypatch.setattr(
        rag,
        "_call_openai",
        lambda operation, call: _mock_model(operation, call, "O prazo é de 15 dias."),
    )

    result = rag.answer_question("Qual é o prazo?")

    assert result["citation_ids"] == []
    assert result["evidence_status"] == "retrieved_not_cited"


@pytest.mark.parametrize("rows", [[], [(17, 91, "manual.pdf", 2, "Trecho.", 0.20)]])
def test_answer_abstains_when_retrieval_has_no_sufficient_evidence(monkeypatch, rows):
    connection = FakeConnection(rows)
    monkeypatch.setattr(rag, "embed", lambda texts: [[0.1, 0.2]])
    monkeypatch.setattr(rag, "connect", lambda: connection)
    monkeypatch.setattr(
        rag,
        "_call_openai",
        lambda *args: pytest.fail("Chat model must not run without sufficient evidence"),
    )

    result = rag.answer_question("Pergunta sem evidência suficiente?")

    assert result["evidence_retrieved"] is False
    assert result["evidence_status"] == "insufficient"
    assert result["groundedness"] == "not_evaluated"
    assert result["evidence"] == []
    assert result["citation_ids"] == []
