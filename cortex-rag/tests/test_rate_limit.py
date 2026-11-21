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


def test_rate_limit_is_atomic_across_concurrent_postgres_connections(monkeypatch):
    """Exercise the UPSERT contention path against the real PostgreSQL service."""
    from concurrent.futures import ThreadPoolExecutor
    import hashlib

    from app.db import connect, init_db

    init_db()
    api_key = "cortex-postgres-concurrency-test-key"
    key_hash = hashlib.sha256(api_key.encode("utf-8")).hexdigest()
    limit = 4

    with connect() as conn:
        conn.execute("DELETE FROM api_rate_limits WHERE key_hash = %s", (key_hash,))
        initial_window = conn.execute(
            "SELECT date_trunc('minute', NOW())"
        ).fetchone()[0]

    monkeypatch.setattr(rate_limit.settings, "api_access_token", api_key)
    monkeypatch.setattr(rate_limit.settings, "api_rate_limit_requests_per_minute", limit)

    def make_request():
        try:
            rate_limit.enforce_api_rate_limit(api_key)
            return "allowed"
        except HTTPException as exc:
            if exc.status_code == 429:
                return "limited"
            raise

    try:
        with ThreadPoolExecutor(max_workers=12) as executor:
            outcomes = list(executor.map(lambda _: make_request(), range(24)))

        with connect() as conn:
            row = conn.execute(
                "SELECT window_start, request_count FROM api_rate_limits WHERE key_hash = %s",
                (key_hash,),
            ).fetchone()
            final_window = conn.execute(
                "SELECT date_trunc('minute', NOW())"
            ).fetchone()[0]

        # Avoid a false failure if this short concurrency test straddles a
        # fixed-window boundary; window rollover is a separate behavior.
        if initial_window != final_window or row[0] != initial_window:
            pytest.skip("Concurrent requests crossed the fixed-window boundary.")

        assert outcomes.count("allowed") == limit
        assert outcomes.count("limited") == 24 - limit
        # The limiter caps persisted counts at limit + 1 as an overflow sentinel.
        assert row[1] == limit + 1
    finally:
        with connect() as conn:
            conn.execute("DELETE FROM api_rate_limits WHERE key_hash = %s", (key_hash,))
