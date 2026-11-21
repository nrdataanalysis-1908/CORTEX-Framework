import uuid

import pytest

from app.main import _resolve_request_id


def test_request_id_preserves_valid_printable_ascii_value():
    request_id = "trace-123:span_456"

    assert _resolve_request_id(request_id) == request_id


@pytest.mark.parametrize(
    "candidate",
    [
        None,
        "",
        "contains space",
        "line-one\\nline-two",
        "tab\\tvalue",
        "non-ascii-ç",
        "x" * 129,
    ],
)
def test_request_id_replaces_missing_or_unsafe_values(candidate):
    resolved = _resolve_request_id(candidate)

    assert len(resolved) == 36
    assert str(uuid.UUID(resolved)) == resolved


def test_request_id_accepts_maximum_length():
    request_id = "a" * 128

    assert _resolve_request_id(request_id) == request_id
