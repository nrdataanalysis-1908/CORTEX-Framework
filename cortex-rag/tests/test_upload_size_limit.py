import asyncio

import pytest
from fastapi import HTTPException

from app.main import MAX_UPLOAD_BYTES, _read_upload_limited


class FakeUpload:
    def __init__(self, size, payload=b""):
        self.size = size
        self.payload = payload
        self.read_calls = []

    async def read(self, size=-1):
        self.read_calls.append(size)
        return self.payload[:size]


def test_known_oversized_upload_is_rejected_before_read():
    upload = FakeUpload(size=MAX_UPLOAD_BYTES + 1, payload=b"must-not-be-read")

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(_read_upload_limited(upload))

    assert exc_info.value.status_code == 413
    assert upload.read_calls == []


def test_unknown_size_upload_uses_bounded_read_and_rejects_overflow():
    upload = FakeUpload(size=None, payload=b"x" * (MAX_UPLOAD_BYTES + 1))

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(_read_upload_limited(upload))

    assert exc_info.value.status_code == 413
    assert upload.read_calls == [MAX_UPLOAD_BYTES + 1]


def test_upload_within_limit_is_returned():
    upload = FakeUpload(size=5, payload=b"hello")

    result = asyncio.run(_read_upload_limited(upload))

    assert result == b"hello"
    assert upload.read_calls == [MAX_UPLOAD_BYTES + 1]
