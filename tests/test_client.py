from __future__ import annotations

from datetime import date
from typing import Any

import httpx
import pytest

from pdfrest import (
    AsyncPdfRestClient,
    PdfRestApiError,
    PdfRestAuthenticationError,
    PdfRestClient,
    PdfRestConfigurationError,
    PdfRestTimeoutError,
    UpResponse,
)

VALID_API_KEY = "12345678-1234-1234-1234-123456789abc"
ANOTHER_VALID_API_KEY = "abcdefab-cdef-abcd-efab-cdefabcdef12"
ASYNC_API_KEY = "fedcba98-7654-3210-fedc-ba9876543210"


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
        assert request.headers["Api-Key"] == VALID_API_KEY
        assert request.url.path == "/up"
        return httpx.Response(200, json=_build_up_response())

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.up()

    assert isinstance(response, UpResponse)
    assert response.release_date == date(2025, 9, 25)


def test_client_reads_api_key_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PDFREST_API_KEY", VALID_API_KEY)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Api-Key"] == VALID_API_KEY
        assert request.url.host == "example.com"
        return httpx.Response(200, json=_build_up_response())

    transport = httpx.MockTransport(handler)
    with PdfRestClient(base_url="https://example.com", transport=transport) as client:
        response = client.up()

    assert response.product == "pdfRest API Toolkit"


def test_missing_api_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)

    with pytest.raises(PdfRestConfigurationError):
        PdfRestClient()


def test_invalid_length_api_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)

    with pytest.raises(PdfRestConfigurationError):
        PdfRestClient(api_key="too-short")


def test_invalid_uuid_api_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    bad_uuid = "12345678-1234-1234-1234-123456789abz"

    with pytest.raises(PdfRestConfigurationError):
        PdfRestClient(api_key=bad_uuid)


def test_client_allows_missing_api_key_for_custom_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)

    def handler(request: httpx.Request) -> httpx.Response:
        assert "Api-Key" not in request.headers
        assert request.url.host == "internal.example"
        return httpx.Response(200, json=_build_up_response())

    transport = httpx.MockTransport(handler)
    with PdfRestClient(
        base_url="https://internal.example", transport=transport
    ) as client:
        response = client.up()

    assert response.status == "OK"


def test_up_with_custom_headers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Api-Key"] == ANOTHER_VALID_API_KEY
        assert request.headers["X-Test-Header"] == "value"
        return httpx.Response(200, json=_build_up_response())

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=ANOTHER_VALID_API_KEY, transport=transport) as client:
        response = client.up(extra_headers={"X-Test-Header": "value"})

    assert response.version == "2.31.1"


def test_up_with_query_and_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PDFREST_API_KEY", VALID_API_KEY)

    captured_timeout: dict[str, float | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["view"] == "full"
        captured_timeout["value"] = request.extensions.get("timeout")
        return httpx.Response(200, json=_build_up_response())

    transport = httpx.MockTransport(handler)
    with PdfRestClient(transport=transport) as client:
        response = client.up(
            extra_query={"view": "full", "unused": None},
            timeout=0.5,
        )

    assert response.product == "pdfRest API Toolkit"
    timeout_value = captured_timeout["value"]
    assert timeout_value is not None
    if isinstance(timeout_value, dict):
        assert all(
            component == pytest.approx(0.5) for component in timeout_value.values()
        )
    else:
        assert timeout_value == pytest.approx(0.5)


def test_up_rejects_extra_body(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PDFREST_API_KEY", VALID_API_KEY)

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_build_up_response())

    transport = httpx.MockTransport(handler)
    with (
        pytest.raises(PdfRestConfigurationError),
        PdfRestClient(transport=transport) as client,
    ):
        client.up(extra_body={"unexpected": "value"})


def test_prepare_request_merges_queries(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PDFREST_API_KEY", "key")
    with PdfRestClient(api_key=VALID_API_KEY) as client:
        request = client.prepare_request(
            "GET",
            "/test",
            query={"base": "value", "skip": None},
            extra_query={"base": "override", "extra": 42, "ignore": None},
        )

    assert request.params == {
        "base": "override",
        "extra": 42,
        "skip": None,
        "ignore": None,
    }


def test_authentication_error_raises_specific_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PDFREST_API_KEY", VALID_API_KEY)

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "The provided key is not valid."})

    transport = httpx.MockTransport(handler)
    with (
        pytest.raises(PdfRestAuthenticationError) as exc_info,
        PdfRestClient(transport=transport) as client,
    ):
        client.up()
    assert "The provided key is not valid." in str(exc_info.value)


def test_authentication_error_handles_non_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PDFREST_API_KEY", VALID_API_KEY)

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="Unauthorized")

    transport = httpx.MockTransport(handler)
    with (
        pytest.raises(PdfRestAuthenticationError) as exc_info,
        PdfRestClient(transport=transport) as client,
    ):
        client.up()
    assert "Authentication with pdfRest failed." in str(exc_info.value)
    assert exc_info.value.response_content == "Unauthorized"


def test_client_raises_for_non_success_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PDFREST_API_KEY", VALID_API_KEY)

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"message": "server error"})

    transport = httpx.MockTransport(handler)
    with (
        pytest.raises(PdfRestApiError) as exc_info,
        PdfRestClient(transport=transport) as client,
    ):
        client.up()
    assert exc_info.value.status_code == 500


@pytest.mark.asyncio
async def test_async_client_up(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PDFREST_API_KEY", ASYNC_API_KEY)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Api-Key"] == ASYNC_API_KEY
        return httpx.Response(200, json=_build_up_response())

    transport = httpx.MockTransport(handler)
    async with AsyncPdfRestClient(transport=transport) as client:
        response = await client.up()

    assert response.status == "OK"


@pytest.mark.asyncio
async def test_async_up_with_query_and_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PDFREST_API_KEY", ASYNC_API_KEY)

    captured_timeout: dict[str, float | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["mode"] == "ping"
        captured_timeout["value"] = request.extensions.get("timeout")
        return httpx.Response(200, json=_build_up_response())

    transport = httpx.MockTransport(handler)
    async with AsyncPdfRestClient(transport=transport) as client:
        response = await client.up(
            extra_query={"mode": "ping"},
            timeout=0.25,
        )

    assert response.status == "OK"
    timeout_value = captured_timeout["value"]
    assert timeout_value is not None
    if isinstance(timeout_value, dict):
        assert all(
            component == pytest.approx(0.25) for component in timeout_value.values()
        )
    else:
        assert timeout_value == pytest.approx(0.25)


@pytest.mark.asyncio
async def test_async_client_translates_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PDFREST_API_KEY", ASYNC_API_KEY)

    def handler(_: httpx.Request) -> httpx.Response:
        message = "timeout"
        raise httpx.TimeoutException(message)

    transport = httpx.MockTransport(handler)
    with pytest.raises(PdfRestTimeoutError):
        async with AsyncPdfRestClient(transport=transport) as client:
            await client.up()


@pytest.mark.asyncio
async def test_async_up_rejects_extra_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PDFREST_API_KEY", ASYNC_API_KEY)

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_build_up_response())

    transport = httpx.MockTransport(handler)
    with pytest.raises(PdfRestConfigurationError):
        async with AsyncPdfRestClient(transport=transport) as client:
            await client.up(extra_body={"unexpected": "value"})


def test_live_client_up(pdfrest_api_key: str, pdfrest_live_base_url: str) -> None:
    with PdfRestClient(
        api_key=pdfrest_api_key, base_url=pdfrest_live_base_url
    ) as client:
        response = client.up()
    assert response.status.upper() == "OK"
    assert response.product


@pytest.mark.asyncio
async def test_live_async_client_up(
    pdfrest_api_key: str, pdfrest_live_base_url: str
) -> None:
    async with AsyncPdfRestClient(
        api_key=pdfrest_api_key, base_url=pdfrest_live_base_url
    ) as client:
        response = await client.up()
    assert response.version
