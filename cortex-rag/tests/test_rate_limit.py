from contextlib import contextmanager

import psycopg
import pytest
from fastapi import HTTPException

from app import rate_limit


class FakeCursor:
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        return self.row


class FakeConnection:
    def __init__(self, row=None, error=None):
        self.row = row
        self.error = error
        self.statement = None
        self.parameters = None

    def execute(self, statement, parameters):
        self.statement = statement
        self.parameters = parameters
        if self.error:
            raise self.error
        return FakeCursor(self.row)


def install_connection(monkeypatch, connection):
    @contextmanager
    def fake_connect():
        yield connection

    monkeypatch.setattr(rate_limit, "connect", fake_connect)


def test_rate_limit_allows_request_under_limit(monkeypatch):
    monkeypatch.setattr(rate_limit.settings, "api_access_token", "a" * 40)
    monkeypatch.setattr(rate_limit.settings, "api_rate_limit_requests_per_minute", 2)
    connection = FakeConnection((1, 37))
    install_connection(monkeypatch, connection)

    assert rate_limit.enforce_api_rate_limit("a" * 40) is None
    assert "ON CONFLICT (key_hash) DO UPDATE" in connection.statement
    assert len(connection.parameters[0]) == 64


def test_rate_limit_rejects_excess_requests_with_retry_after(monkeypatch):
    monkeypatch.setattr(rate_limit.settings, "api_access_token", "a" * 40)
    monkeypatch.setattr(rate_limit.settings, "api_rate_limit_requests_per_minute", 2)
    install_connection(monkeypatch, FakeConnection((3, 22)))

    with pytest.raises(HTTPException) as exc_info:
        rate_limit.enforce_api_rate_limit("a" * 40)

    assert exc_info.value.status_code == 429
    assert exc_info.value.headers["Retry-After"] == "22"


def test_invalid_key_is_rejected_before_database_access(monkeypatch):
    monkeypatch.setattr(rate_limit.settings, "api_access_token", "a" * 40)

    with pytest.raises(HTTPException) as exc_info:
        rate_limit.enforce_api_rate_limit("wrong")

    assert exc_info.value.status_code == 401


def test_rate_limit_fails_closed_when_database_is_unavailable(monkeypatch):
    monkeypatch.setattr(rate_limit.settings, "api_access_token", "a" * 40)
    install_connection(monkeypatch, FakeConnection(error=psycopg.OperationalError("offline")))

    with pytest.raises(HTTPException) as exc_info:
        rate_limit.enforce_api_rate_limit("a" * 40)

    assert exc_info.value.status_code == 503
    assert exc_info.value.headers["Retry-After"] == "5"
