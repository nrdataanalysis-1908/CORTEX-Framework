class RequestBodyTooLarge(Exception):
    """Raised when an incoming HTTP request exceeds its configured body limit."""


class RequestBodyLimitMiddleware:
    """Bound request-body bytes before Starlette parses multipart uploads.

    The middleware counts streamed ASGI messages without buffering the body.
    """

    def __init__(self, app, max_body_bytes: int, protected_path: str):
        if max_body_bytes <= 0:
            raise ValueError("max_body_bytes must be positive")
        if not protected_path.startswith("/"):
            raise ValueError("protected_path must be an absolute path")
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

        content_lengths = [
            value for name, value in scope.get("headers", [])
            if name.lower() == b"content-length"
        ]
        if content_lengths:
            if len(content_lengths) != 1:
                await self._send_error(send, 400, "Invalid Content-Length header.")
                return
            raw_length = content_lengths[0]
            if not raw_length or not raw_length.isdigit():
                await self._send_error(send, 400, "Invalid Content-Length header.")
                return
            if int(raw_length) > self.max_body_bytes:
                await self._send_error(send, 413, "Request body exceeds the configured limit.")
                return

        received_bytes = 0
        response_started = False

        async def limited_receive():
            nonlocal received_bytes
            message = await receive()
            if message.get("type") == "http.request":
                received_bytes += len(message.get("body", b""))
                if received_bytes > self.max_body_bytes:
                    raise RequestBodyTooLarge
            return message

        async def tracked_send(message):
            nonlocal response_started
            if message.get("type") == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, tracked_send)
        except RequestBodyTooLarge:
            # ASGI forbids a second response.start. If the downstream app has
            # already started its response, propagate the exception so the
            # server terminates the incomplete response instead of double-send.
            if response_started:
                raise
            await self._send_error(
                send, 413, "Request body exceeds the configured limit."
            )

    @staticmethod
    async def _send_error(send, status_code: int, detail: str):
        body = ('{"detail":"' + detail + '"}').encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": status_code,
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
