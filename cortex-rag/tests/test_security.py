import pytest
from fastapi import HTTPException

from app import security


def test_api_key_is_accepted(monkeypatch):
    monkeypatch.setattr(security.settings, "api_access_token", "a" * 40)

    assert security.require_api_key("a" * 40) is None


@pytest.mark.parametrize("provided_key", [None, "wrong-key"])
def test_missing_or_invalid_api_key_is_rejected(monkeypatch, provided_key):
    monkeypatch.setattr(security.settings, "api_access_token", "a" * 40)

    with pytest.raises(HTTPException) as exc_info:
        security.require_api_key(provided_key)

    assert exc_info.value.status_code == 401
    assert exc_info.value.headers["WWW-Authenticate"] == "ApiKey"


def test_unconfigured_api_key_fails_closed(monkeypatch):
    monkeypatch.setattr(security.settings, "api_access_token", None)

    with pytest.raises(HTTPException) as exc_info:
        security.require_api_key("any-value")

    assert exc_info.value.status_code == 503
