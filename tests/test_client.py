from __future__ import annotations

import os
from datetime import date
from typing import Any

import httpx
import pytest

from pdfrest import (
    AsyncPdfRestClient,
    PdfRestApiError,
    PdfRestClient,
    PdfRestConfigurationError,
    PdfRestTimeoutError,
    RequestOptions,
    UpResponse,
)

LIVE_BASE_URL_CANDIDATES: tuple[str, ...] = (
    "http://localhost:3000",
    "https://apidev.pdfrest.com",
    "https://api.pdfrest.com",
)


def _build_up_response() -> dict[str, Any]:
    return {
        "status": "OK",
        "product": "pdfRest API Toolkit",
        "releaseDate": "2025-09-25",
        "version": "2.31.1",
    }


def test_client_uses_provided_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer explicit-key"
        assert request.url.path == "/up"
        return httpx.Response(200, json=_build_up_response())

    transport = httpx.MockTransport(handler)
    client = PdfRestClient(api_key="explicit-key", transport=transport)
    try:
        response = client.up()
    finally:
        client.close()

    assert isinstance(response, UpResponse)
    assert response.release_date == date(2025, 9, 25)


def test_client_reads_api_key_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PDFREST_API_KEY", "environment-key")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer environment-key"
        assert request.url.host == "example.com"
        return httpx.Response(200, json=_build_up_response())

    transport = httpx.MockTransport(handler)
    client = PdfRestClient(base_url="https://example.com", transport=transport)
    try:
        response = client.up()
    finally:
        client.close()

    assert response.product == "pdfRest API Toolkit"


def test_missing_api_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)

    with pytest.raises(PdfRestConfigurationError):
        PdfRestClient()


def test_up_with_custom_headers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer custom-key"
        assert request.headers["X-Test-Header"] == "value"
        return httpx.Response(200, json=_build_up_response())

    transport = httpx.MockTransport(handler)
    client = PdfRestClient(api_key="custom-key", transport=transport)
    options: RequestOptions = {"headers": {"X-Test-Header": "value"}}
    try:
        response = client.up(options=options)
    finally:
        client.close()

    assert response.version == "2.31.1"


def test_client_raises_for_non_success_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PDFREST_API_KEY", "key")

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"message": "server error"})

    transport = httpx.MockTransport(handler)
    client = PdfRestClient(transport=transport)

    with pytest.raises(PdfRestApiError) as exc_info:
        client.up()

    client.close()
    assert exc_info.value.status_code == 500


@pytest.mark.asyncio
async def test_async_client_up(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PDFREST_API_KEY", "async-key")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer async-key"
        return httpx.Response(200, json=_build_up_response())

    transport = httpx.MockTransport(handler)
    client = AsyncPdfRestClient(transport=transport)
    async with client:
        response = await client.up()

    assert response.status == "OK"


@pytest.mark.asyncio
async def test_async_client_translates_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PDFREST_API_KEY", "async-key")

    def handler(_: httpx.Request) -> httpx.Response:
        message = "timeout"
        raise httpx.TimeoutException(message)

    transport = httpx.MockTransport(handler)
    client = AsyncPdfRestClient(transport=transport)

    with pytest.raises(PdfRestTimeoutError):
        async with client:
            await client.up()


@pytest.fixture(scope="session")
def pdfrest_api_key() -> str:
    key = os.getenv("PDFREST_API_KEY")
    if not key:
        pytest.fail("PDFREST_API_KEY is not configured.")
    return key


@pytest.fixture(scope="session")
def pdfrest_live_base_url(pdfrest_api_key: str) -> str:
    headers = {"Authorization": f"Bearer {pdfrest_api_key}"}
    timeout = httpx.Timeout(2.0)
    for base_url in LIVE_BASE_URL_CANDIDATES:
        try:
            with httpx.Client(base_url=base_url, timeout=timeout) as client:
                response = client.get("/up", headers=headers)
        except httpx.HTTPError:
            continue
        if response.is_success:
            return base_url
    pytest.fail("No reachable pdfRest API instance for live tests.")


def test_live_client_up(pdfrest_api_key: str, pdfrest_live_base_url: str) -> None:
    client = PdfRestClient(api_key=pdfrest_api_key, base_url=pdfrest_live_base_url)
    try:
        response = client.up()
    finally:
        client.close()
    assert response.status.upper() == "OK"
    assert response.product


@pytest.mark.asyncio
async def test_live_async_client_up(
    pdfrest_api_key: str, pdfrest_live_base_url: str
) -> None:
    client = AsyncPdfRestClient(api_key=pdfrest_api_key, base_url=pdfrest_live_base_url)
    async with client:
        response = await client.up()
    assert response.version
