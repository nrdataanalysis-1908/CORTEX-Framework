import os

os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/cortex")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-placeholder")

import psycopg
from fastapi.testclient import TestClient

from app import main


def test_liveness_remains_available_when_database_initialization_fails(monkeypatch):
    def fail_initialization():
        raise psycopg.OperationalError("database unavailable")

    monkeypatch.setattr(main, "init_db", fail_initialization)

    with TestClient(main.app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["check"] == "liveness"


def test_readiness_returns_503_when_database_or_schema_is_unavailable(monkeypatch):
    monkeypatch.setattr(main, "init_db", lambda: None)
    monkeypatch.setattr(main, "check_database", lambda: False)

    with TestClient(main.app) as client:
        response = client.get("/ready")

    assert response.status_code == 503


def test_readiness_returns_200_when_database_schema_is_available(monkeypatch):
    monkeypatch.setattr(main, "init_db", lambda: None)
    monkeypatch.setattr(main, "check_database", lambda: True)

    with TestClient(main.app) as client:
        response = client.get("/ready")

    assert response.status_code == 200
    assert response.json()["database"] == "available"
