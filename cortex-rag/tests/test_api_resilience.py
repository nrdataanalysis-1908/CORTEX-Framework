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

    
def test_protected_endpoints_reject_missing_and_invalid_api_keys(monkeypatch):
    monkeypatch.setattr(main.settings, "cortex_api_key", "test-api-key-value-with-32-chars")
    with TestClient(main.app) as client:
        missing = client.get("/metrics")
        invalid = client.get("/metrics", headers={"X-API-Key": "wrong-key"})

    assert missing.status_code == 401
    assert invalid.status_code == 401
    assert missing.headers["www-authenticate"] == "ApiKey"


def test_protected_metrics_endpoint_accepts_valid_api_key(monkeypatch):
    api_key = "test-api-key-value-with-32-chars"
    monkeypatch.setattr(main.settings, "cortex_api_key", api_key)
    with TestClient(main.app) as client:
        response = client.get("/metrics", headers={"X-API-Key": api_key})

    assert response.status_code == 200
    assert response.json()["scope"] == "process_local"


def test_health_and_readiness_remain_public(monkeypatch):
    monkeypatch.setattr(main, "init_db", lambda: None)
    monkeypatch.setattr(main, "check_database", lambda: True)
    with TestClient(main.app) as client:
        health = client.get("/health")
        readiness = client.get("/ready")

    assert health.status_code == 200
    assert readiness.status_code == 200
