import asyncio

import pytest
from fastapi import HTTPException

from app.main import MAX_UPLOAD_BYTES, _read_upload_limited


class FakeUpload:
    def __init__(self, size, payload):
        self.size = size
        self.payload = payload
        self.read_calls = []

    async def read(self, limit=-1):
        self.read_calls.append(limit)
        return self.payload[:limit]


def test_upload_exactly_at_15_mib_limit_is_accepted():
    payload = b"x" * MAX_UPLOAD_BYTES
    upload = FakeUpload(size=MAX_UPLOAD_BYTES, payload=payload)

    result = asyncio.run(_read_upload_limited(upload))

    assert len(result) == MAX_UPLOAD_BYTES
    assert upload.read_calls == [MAX_UPLOAD_BYTES + 1]


def test_upload_one_byte_over_15_mib_is_rejected():
    payload = b"x" * (MAX_UPLOAD_BYTES + 1)
    upload = FakeUpload(size=MAX_UPLOAD_BYTES + 1, payload=payload)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(_read_upload_limited(upload))

    assert exc_info.value.status_code == 413
    assert upload.read_calls == []
