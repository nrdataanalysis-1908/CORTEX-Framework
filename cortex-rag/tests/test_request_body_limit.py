import asyncio

import pytest

from app.request_limits import RequestBodyLimitMiddleware


def run_asgi(app, scope, messages):
    sent = []
    iterator = iter(messages)

    async def receive():
        try:
            return next(iterator)
        except StopIteration:
            return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent.append(message)

    asyncio.run(app(scope, receive, send))
    return sent


def make_scope(path="/documents", method="POST", headers=None):
    return {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("ascii"),
        "query_string": b"",
        "headers": headers or [],
        "server": ("testserver", 80),
        "client": ("127.0.0.1", 12345),
    }


def consuming_app(called):
    async def app(scope, receive, send):
        called.append(True)
        while True:
            message = await receive()
            if message.get("type") != "http.request" or not message.get("more_body", False):
                break
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok", "more_body": False})

    return app


def response_status(messages):
    return next(message["status"] for message in messages if message["type"] == "http.response.start")


def middleware(app, limit=10):
    return RequestBodyLimitMiddleware(app, max_body_bytes=limit, protected_path="/documents")


def test_content_length_over_limit_is_rejected_before_application_runs():
    called = []
    sent = run_asgi(
        middleware(consuming_app(called)),
        make_scope(headers=[(b"content-length", b"11")]),
        [],
    )
    assert response_status(sent) == 413
    assert called == []


def test_chunked_body_over_limit_is_rejected_without_content_length():
    called = []
    sent = run_asgi(
        middleware(consuming_app(called)),
        make_scope(),
        [
            {"type": "http.request", "body": b"123456", "more_body": True},
            {"type": "http.request", "body": b"78901", "more_body": False},
        ],
    )
    assert response_status(sent) == 413
    assert called == [True]


def test_chunked_body_exactly_at_limit_is_accepted():
    called = []
    sent = run_asgi(
        middleware(consuming_app(called)),
        make_scope(),
        [
            {"type": "http.request", "body": b"1234", "more_body": True},
            {"type": "http.request", "body": b"567890", "more_body": False},
        ],
    )
    assert response_status(sent) == 200
    assert called == [True]


def test_other_paths_are_not_affected_by_upload_body_limit():
    called = []
    sent = run_asgi(
        middleware(consuming_app(called)),
        make_scope(path="/ask", headers=[(b"content-length", b"999")]),
        [],
    )
    assert response_status(sent) == 200
    assert called == [True]


@pytest.mark.parametrize(
    "headers",
    [
        [(b"content-length", b"5"), (b"content-length", b"5")],
        [(b"content-length", b"+5")],
        [(b"content-length", b"-1")],
    ],
)
def test_ambiguous_or_invalid_content_length_is_rejected(headers):
    called = []
    sent = run_asgi(
        middleware(consuming_app(called)),
        make_scope(headers=headers),
        [],
    )
    assert response_status(sent) == 400
    assert called == []


def test_zero_content_length_is_valid():
    called = []
    sent = run_asgi(
        middleware(consuming_app(called)),
        make_scope(headers=[(b"content-length", b"0")]),
        [{"type": "http.request", "body": b"", "more_body": False}],
    )
    assert response_status(sent) == 200
    assert called == [True]


def test_disconnect_message_is_forwarded_without_counting_as_body():
    observed = []

    async def app(scope, receive, send):
        observed.append(await receive())

    sent = run_asgi(
        middleware(app),
        make_scope(),
        [{"type": "http.disconnect"}],
    )
    assert observed == [{"type": "http.disconnect"}]
    assert sent == []


def test_overflow_after_response_started_does_not_send_a_second_response_start():
    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await receive()

    sent = []
    messages = iter([{"type": "http.request", "body": b"01234567890", "more_body": False}])

    async def receive():
        return next(messages)

    async def send(message):
        sent.append(message)

    with pytest.raises(Exception, match=""):
        asyncio.run(middleware(app)(make_scope(), receive, send))

    assert [m["type"] for m in sent].count("http.response.start") == 1


@pytest.mark.parametrize(
    "limit,path",
    [(0, "/documents"), (-1, "/documents"), (10, "documents")],
)
def test_invalid_middleware_configuration_is_rejected(limit, path):
    with pytest.raises(ValueError):
        RequestBodyLimitMiddleware(consuming_app([]), limit, path)
