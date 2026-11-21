import asyncio

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


def test_content_length_over_limit_is_rejected_before_application_runs():
    called = []
    middleware = RequestBodyLimitMiddleware(
        consuming_app(called), max_body_bytes=10, protected_path="/documents"
    )
    sent = run_asgi(
        middleware,
        make_scope(headers=[(b"content-length", b"11")]),
        [],
    )

    assert response_status(sent) == 413
    assert called == []


def test_chunked_body_over_limit_is_rejected_without_content_length():
    called = []
    middleware = RequestBodyLimitMiddleware(
        consuming_app(called), max_body_bytes=10, protected_path="/documents"
    )
    sent = run_asgi(
        middleware,
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
    middleware = RequestBodyLimitMiddleware(
        consuming_app(called), max_body_bytes=10, protected_path="/documents"
    )
    sent = run_asgi(
        middleware,
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
    middleware = RequestBodyLimitMiddleware(
        consuming_app(called), max_body_bytes=10, protected_path="/documents"
    )
    sent = run_asgi(
        middleware,
        make_scope(path="/ask", headers=[(b"content-length", b"999")]),
        [],
    )

    assert response_status(sent) == 200
    assert called == [True]
