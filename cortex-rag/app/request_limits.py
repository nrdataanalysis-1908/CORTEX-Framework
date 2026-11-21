class RequestBodyTooLarge(Exception):
    """Raised when an incoming HTTP request exceeds its configured body limit."""


class RequestBodyLimitMiddleware:
    """Bound request-body bytes before Starlette parses multipart uploads.

    The middleware counts streamed ASGI messages, so chunked requests without a
    Content-Length header are covered as well. It only applies to the configured
    upload endpoint and does not buffer the request body.
    """

    def __init__(self, app, max_body_bytes: int, protected_path: str):
        if max_body_bytes <= 0:
            raise ValueError("max_body_bytes must be positive")
        self.app = app
        self.max_body_bytes = max_body_bytes
        self.protected_path = protected_path

    async def __call__(self, scope, receive, send):
        if (
            scope.get("type") != "http"
            or scope.get("method") != "POST"
            or scope.get("path") != self.protected_path
        ):
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        content_length = headers.get(b"content-length")
        if content_length is not None:
            try:
                declared_length = int(content_length)
            except (TypeError, ValueError):
                declared_length = None
            if declared_length is not None and declared_length > self.max_body_bytes:
                await self._send_too_large(send)
                return

        received_bytes = 0

        async def limited_receive():
            nonlocal received_bytes
            message = await receive()
            if message.get("type") == "http.request":
                received_bytes += len(message.get("body", b""))
                if received_bytes > self.max_body_bytes:
                    raise RequestBodyTooLarge
            return message

        try:
            await self.app(scope, limited_receive, send)
        except RequestBodyTooLarge:
            await self._send_too_large(send)

    @staticmethod
    async def _send_too_large(send):
        body = b'{"detail":"Request body exceeds the configured limit."}'
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("ascii")),
                ],
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": body,
                "more_body": False,
            }
        )
