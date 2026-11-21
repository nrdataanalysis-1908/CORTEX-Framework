import asyncio

import httpx
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.applications import Starlette

from app.request_limits import RequestBodyLimitMiddleware


async def consume_document(request: Request):
    body = await request.body()
    return JSONResponse({"received": len(body)})


async def consume_question(request: Request):
    body = await request.body()
    return JSONResponse({"received": len(body)})


def build_http_app(limit=10):
    application = Starlette(
        routes=[
            Route("/documents", consume_document, methods=["POST"]),
            Route("/ask", consume_question, methods=["POST"]),
        ]
    )
    return RequestBodyLimitMiddleware(
        application,
        max_body_bytes=limit,
        protected_path="/documents",
    )


def request(method, path, content):
    async def execute():
        transport = httpx.ASGITransport(app=build_http_app())
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.request(method, path, content=content)

    return asyncio.run(execute())


def test_http_upload_over_limit_returns_413_before_route_consumes_body():
    response = request("POST", "/documents", b"01234567890")

    assert response.status_code == 413
    assert response.json() == {
        "detail": "Request body exceeds the configured limit."
    }


def test_http_upload_at_exact_limit_reaches_route():
    response = request("POST", "/documents", b"0123456789")

    assert response.status_code == 200
    assert response.json() == {"received": 10}


def test_http_other_post_route_is_not_restricted_by_upload_limit():
    response = request("POST", "/ask", b"01234567890123456789")

    assert response.status_code == 200
    assert response.json() == {"received": 20}
