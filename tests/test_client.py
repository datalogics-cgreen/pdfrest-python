from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from email.utils import format_datetime
from io import BytesIO, UnsupportedOperation
from pathlib import Path
from typing import Any

import httpx
import pytest
from typing_extensions import override

from pdfrest import (
    AsyncPdfRestClient,
    PdfRestApiError,
    PdfRestAuthenticationError,
    PdfRestClient,
    PdfRestConfigurationError,
    PdfRestTimeoutError,
    PdfRestTransportError,
    UpResponse,
    client as client_module,
)

VALID_API_KEY = "12345678-1234-1234-1234-123456789abc"
ANOTHER_VALID_API_KEY = "abcdefab-cdef-abcd-efab-cdefabcdef12"
ASYNC_API_KEY = "fedcba98-7654-3210-fedc-ba9876543210"
DEMO_RESTRICTION_MESSAGE = (
    "Output has been watermarked or redacted. This API request was processed "
    "with a free account. Visit https://pdfrest.com/pricing/ to upgrade your "
    "plan and receive outputs without watermarks or redactions."
)


def _build_up_response() -> dict[str, Any]:
    return {
        "status": "OK",
        "product": "pdfRest API Toolkit",
        "releaseDate": "2025-09-25",
        "version": "2.31.1",
    }


def _build_file_info(
    file_id: str = "1de305d2-b6a0-4b5d-9a55-4e4e6d8c2d39",
) -> dict[str, Any]:
    return {
        "id": file_id,
        "name": "sample.pdf",
        "url": "https://files.example.com/sample.pdf",
        "type": "application/pdf",
        "size": 1024,
        "modified": "2024-01-01T00:00:00+00:00",
        "scheduledDeletionTimeUtc": "2024-01-02T00:00:00+00:00",
    }


def _build_error_detail_response() -> dict[str, Any]:
    return {
        "error": "-.8 is not within the acceptable range for opacity",
        "errorDetail": {
            "issues": [
                {
                    "path": "fields.text_objects[0].opacity",
                    "message": "Too small: expected number to be >=0",
                    "minimum": 0,
                    "maximum": 1,
                },
                {
                    "path": "fields.text_objects[0].text_color_cmyk[2]",
                    "message": (
                        'Invalid text_color_cmyk yellow value "foo" (expected 0-100).'
                    ),
                    "minimum": 0,
                    "maximum": 100,
                },
            ]
        },
    }


class NonSeekableByteStream(BytesIO):
    def __init__(self, payload: bytes) -> None:
        super().__init__(payload)

    @override
    def seek(self, *args: Any, **kwargs: Any) -> int:
        msg = "non-seekable"
        raise UnsupportedOperation(msg)

    @override
    def tell(self) -> int:
        msg = "non-seekable"
        raise UnsupportedOperation(msg)


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


def test_client_sets_sdk_headers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PDFREST_API_KEY", VALID_API_KEY)
    monkeypatch.setattr(client_module.importlib.metadata, "version", lambda _: "1.2.3")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["wsn"] == "pdfrest-python"
        assert request.headers["User-Agent"] == "pdfrest-python-sdk/1.2.3"
        assert request.headers["Accept"] == "application/json"
        return httpx.Response(200, json=_build_up_response())

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        client.up()


@pytest.mark.asyncio
async def test_async_client_sets_sdk_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PDFREST_API_KEY", ASYNC_API_KEY)
    monkeypatch.setattr(client_module.importlib.metadata, "version", lambda _: "4.5.6")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["wsn"] == "pdfrest-python"
        assert request.headers["User-Agent"] == "pdfrest-python-sdk/4.5.6"
        assert request.headers["Accept"] == "application/json"
        return httpx.Response(200, json=_build_up_response())

    transport = httpx.MockTransport(handler)
    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        await client.up()


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


def test_client_retries_on_server_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PDFREST_API_KEY", VALID_API_KEY)
    monkeypatch.setattr(client_module.random, "uniform", lambda *_: 0.0)
    sleep_calls: list[float] = []
    monkeypatch.setattr(
        client_module.time, "sleep", lambda delay: sleep_calls.append(delay)
    )

    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:  # pyright: ignore[reportUnusedParameter]
        attempts["count"] += 1
        if attempts["count"] < 3:
            return httpx.Response(500, json={"error": "try-again"})
        return httpx.Response(200, json=_build_up_response())

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.up()

    assert attempts["count"] == 3
    assert response.status == "OK"
    assert sleep_calls == [0.5, 1.0]


def test_client_retry_honors_retry_after_seconds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PDFREST_API_KEY", VALID_API_KEY)
    monkeypatch.setattr(client_module.random, "uniform", lambda *_: 0.0)
    sleep_calls: list[float] = []
    monkeypatch.setattr(
        client_module.time, "sleep", lambda delay: sleep_calls.append(delay)
    )

    attempts = {"count": 0}

    def handler(_: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        if attempts["count"] == 1:
            return httpx.Response(
                429,
                headers={"Retry-After": "2"},
                json={"error": "slow down"},
            )
        return httpx.Response(200, json=_build_up_response())

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.up()

    assert response.status == "OK"
    assert attempts["count"] == 2
    assert sleep_calls == [pytest.approx(2.0)]


def test_client_retry_honors_retry_after_http_date(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PDFREST_API_KEY", VALID_API_KEY)
    monkeypatch.setattr(client_module.random, "uniform", lambda *_: 0.0)
    sleep_calls: list[float] = []
    monkeypatch.setattr(
        client_module.time, "sleep", lambda delay: sleep_calls.append(delay)
    )

    attempts = {"count": 0}
    retry_after = format_datetime(datetime.now(timezone.utc) + timedelta(seconds=3))

    def handler(_: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        if attempts["count"] == 1:
            return httpx.Response(
                503,
                headers={"Retry-After": retry_after},
                json={"error": "busy"},
            )
        return httpx.Response(200, json=_build_up_response())

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.up()

    assert response.status == "OK"
    assert attempts["count"] == 2
    assert sleep_calls
    assert sleep_calls[0] >= 2.0


def test_client_retries_on_timeout_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PDFREST_API_KEY", VALID_API_KEY)
    monkeypatch.setattr(client_module.random, "uniform", lambda *_: 0.0)
    sleep_calls: list[float] = []
    monkeypatch.setattr(
        client_module.time, "sleep", lambda delay: sleep_calls.append(delay)
    )

    attempts = {"count": 0}

    def handler(_: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        if attempts["count"] == 1:
            msg = "timeout"
            raise httpx.TimeoutException(msg)
        return httpx.Response(200, json=_build_up_response())

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.up()

    assert response.status == "OK"
    assert attempts["count"] == 2
    assert sleep_calls == [0.5]


def test_client_retries_on_408_status(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PDFREST_API_KEY", VALID_API_KEY)
    monkeypatch.setattr(client_module.random, "uniform", lambda *_: 0.0)
    sleep_calls: list[float] = []
    monkeypatch.setattr(
        client_module.time, "sleep", lambda delay: sleep_calls.append(delay)
    )

    attempts = {"count": 0}

    def handler(_: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        if attempts["count"] == 1:
            return httpx.Response(408, text="timeout")
        return httpx.Response(200, json=_build_up_response())

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.up()

    assert response.status == "OK"
    assert attempts["count"] == 2
    assert sleep_calls == [0.5]


def test_client_raises_after_retry_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PDFREST_API_KEY", VALID_API_KEY)
    monkeypatch.setattr(client_module.random, "uniform", lambda *_: 0.0)
    sleep_calls: list[float] = []
    monkeypatch.setattr(
        client_module.time, "sleep", lambda delay: sleep_calls.append(delay)
    )

    attempts = {"count": 0}

    def handler(_: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        return httpx.Response(503, json={"error": "busy"})

    transport = httpx.MockTransport(handler)
    with (
        pytest.raises(PdfRestApiError),
        PdfRestClient(
            api_key=VALID_API_KEY, transport=transport, max_retries=1
        ) as client,
    ):
        client.up()

    assert attempts["count"] == 2
    assert sleep_calls == [0.5]


@pytest.mark.asyncio
async def test_async_client_retries_on_server_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PDFREST_API_KEY", ASYNC_API_KEY)
    monkeypatch.setattr(client_module.random, "uniform", lambda *_: 0.0)
    sleep_calls: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    monkeypatch.setattr(client_module.asyncio, "sleep", fake_sleep)

    attempts = {"count": 0}

    async def handler(request: httpx.Request) -> httpx.Response:  # pyright: ignore[reportUnusedParameter]
        attempts["count"] += 1
        if attempts["count"] < 3:
            return httpx.Response(503, json={"error": "retry"})
        return httpx.Response(200, json=_build_up_response())

    transport = httpx.MockTransport(handler)
    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        response = await client.up()

    assert attempts["count"] == 3
    assert response.status == "OK"
    assert sleep_calls == [0.5, 1.0]


@pytest.mark.asyncio
async def test_async_client_retries_on_timeout_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PDFREST_API_KEY", ASYNC_API_KEY)
    monkeypatch.setattr(client_module.random, "uniform", lambda *_: 0.0)
    sleep_calls: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    monkeypatch.setattr(client_module.asyncio, "sleep", fake_sleep)

    attempts = {"count": 0}

    async def handler(_: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        if attempts["count"] == 1:
            msg = "timeout"
            raise httpx.TimeoutException(msg)
        return httpx.Response(200, json=_build_up_response())

    transport = httpx.MockTransport(handler)
    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        response = await client.up()

    assert response.status == "OK"
    assert attempts["count"] == 2
    assert sleep_calls == [0.5]


@pytest.mark.asyncio
async def test_async_client_retry_honors_retry_after_seconds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PDFREST_API_KEY", ASYNC_API_KEY)
    monkeypatch.setattr(client_module.random, "uniform", lambda *_: 0.0)
    sleep_calls: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    monkeypatch.setattr(client_module.asyncio, "sleep", fake_sleep)

    attempts = {"count": 0}

    async def handler(_: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        if attempts["count"] == 1:
            return httpx.Response(
                429,
                headers={"Retry-After": "4"},
                json={"error": "slow"},
            )
        return httpx.Response(200, json=_build_up_response())

    transport = httpx.MockTransport(handler)
    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        response = await client.up()

    assert response.status == "OK"
    assert attempts["count"] == 2
    assert sleep_calls == [pytest.approx(4.0)]


def test_client_rejects_negative_max_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PDFREST_API_KEY", VALID_API_KEY)

    with pytest.raises(PdfRestConfigurationError):
        PdfRestClient(max_retries=-1)


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


def test_prepare_request_rejects_files_with_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PDFREST_API_KEY", VALID_API_KEY)
    with (
        PdfRestClient(api_key=VALID_API_KEY) as client,
        pytest.raises(
            PdfRestConfigurationError,
            match="JSON payloads cannot be combined with multipart file uploads",
        ),
    ):
        client.prepare_request(
            "POST",
            "/upload",
            json_body={"foo": "bar"},
            files=[("file", b"data")],
        )


def test_prepare_request_rejects_missing_leading_slash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PDFREST_API_KEY", VALID_API_KEY)
    with (
        PdfRestClient(api_key=VALID_API_KEY) as client,
        pytest.raises(PdfRestConfigurationError, match="endpoint must start with '/'"),
    ):
        client.prepare_request("GET", "up")


@pytest.mark.asyncio
async def test_async_prepare_request_rejects_missing_leading_slash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PDFREST_API_KEY", ASYNC_API_KEY)
    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY) as client:
        with pytest.raises(
            PdfRestConfigurationError, match="endpoint must start with '/'"
        ):
            client.prepare_request("GET", "up")


def test_prepare_request_accepts_iterator_and_marks_stream(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PDFREST_API_KEY", VALID_API_KEY)
    file_iter = iter([("file", BytesIO(b"data"))])
    with PdfRestClient(api_key=VALID_API_KEY) as client:
        request = client.prepare_request("POST", "/upload", files=file_iter)

    assert isinstance(request.files, list)
    assert len(request.files) == 1
    assert request.has_stream_uploads()


@pytest.mark.asyncio
async def test_async_prepare_request_accepts_iterator_and_marks_stream(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PDFREST_API_KEY", ASYNC_API_KEY)
    file_iter = iter([("file", BytesIO(b"data"))])
    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY) as client:
        request = client.prepare_request("POST", "/upload", files=file_iter)

    assert isinstance(request.files, list)
    assert len(request.files) == 1
    assert request.has_stream_uploads()


def test_download_file_retries_on_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PDFREST_API_KEY", VALID_API_KEY)
    monkeypatch.setattr(client_module.random, "uniform", lambda *_: 0.0)
    sleep_calls: list[float] = []
    monkeypatch.setattr(
        client_module.time, "sleep", lambda delay: sleep_calls.append(delay)
    )

    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/resource/file-123":
            attempts["count"] += 1
            if attempts["count"] == 1:
                return httpx.Response(503, json={"error": "retry"})
            return httpx.Response(200, content=b"file-bytes")
        msg = f"Unexpected path {request.url.path}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.download_file("file-123")
        try:
            payload = response.read()
        finally:
            response.close()

    assert payload == b"file-bytes"
    assert attempts["count"] == 2
    assert sleep_calls == [0.5]


@pytest.mark.asyncio
async def test_async_download_file_retries_on_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PDFREST_API_KEY", ASYNC_API_KEY)
    monkeypatch.setattr(client_module.random, "uniform", lambda *_: 0.0)
    sleep_calls: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    monkeypatch.setattr(client_module.asyncio, "sleep", fake_sleep)

    attempts = {"count": 0}

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/resource/async-file":
            attempts["count"] += 1
            if attempts["count"] == 1:
                return httpx.Response(500, json={"error": "retry"})
            return httpx.Response(200, content=b"async-bytes")
        msg = f"Unexpected path {request.url.path}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        response = await client.download_file("async-file")
        try:
            payload = await response.aread()
        finally:
            await response.aclose()

    assert payload == b"async-bytes"
    assert attempts["count"] == 2
    assert sleep_calls == [0.5]


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


def test_client_raises_for_non_json_success_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PDFREST_API_KEY", VALID_API_KEY)

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="not-json")

    transport = httpx.MockTransport(handler)
    with (
        pytest.raises(PdfRestApiError, match="Response body is not valid JSON") as exc,
        PdfRestClient(transport=transport) as client,
    ):
        client.up()
    assert exc.value.status_code == 200
    assert exc.value.response_content == "not-json"


def test_client_logs_demo_restriction_message_warning(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("PDFREST_API_KEY", VALID_API_KEY)
    caplog.set_level("WARNING", logger="pdfrest.client")

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={**_build_up_response(), "message": DEMO_RESTRICTION_MESSAGE},
        )

    transport = httpx.MockTransport(handler)
    with PdfRestClient(transport=transport) as client:
        _ = client.up()

    assert "Demo mode restriction message in response" in caplog.text
    assert "field=message" in caplog.text
    assert DEMO_RESTRICTION_MESSAGE in caplog.text


@pytest.mark.parametrize(
    ("field_name", "body_value"),
    [
        pytest.param("message", DEMO_RESTRICTION_MESSAGE, id="message"),
        pytest.param("warning", DEMO_RESTRICTION_MESSAGE, id="warning"),
        pytest.param("keyMessage", DEMO_RESTRICTION_MESSAGE, id="key-message"),
    ],
)
def test_client_logs_demo_restriction_message_warning_all_fields(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    field_name: str,
    body_value: str,
) -> None:
    monkeypatch.setenv("PDFREST_API_KEY", VALID_API_KEY)
    caplog.set_level("WARNING", logger="pdfrest.client")

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={**_build_up_response(), field_name: body_value},
        )

    transport = httpx.MockTransport(handler)
    with PdfRestClient(transport=transport) as client:
        _ = client.up()

    assert "Demo mode restriction message in response" in caplog.text
    assert f"field={field_name}" in caplog.text
    assert DEMO_RESTRICTION_MESSAGE in caplog.text


def test_client_logs_demo_restriction_message_once_when_duplicated(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("PDFREST_API_KEY", VALID_API_KEY)
    caplog.set_level("WARNING", logger="pdfrest.client")

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                **_build_up_response(),
                "message": DEMO_RESTRICTION_MESSAGE,
                "warning": DEMO_RESTRICTION_MESSAGE,
                "keyMessage": DEMO_RESTRICTION_MESSAGE,
            },
        )

    transport = httpx.MockTransport(handler)
    with PdfRestClient(transport=transport) as client:
        _ = client.up()

    demo_logs = [
        record.message
        for record in caplog.records
        if "Demo mode restriction message in response" in record.message
    ]
    assert len(demo_logs) == 1


def test_client_does_not_log_non_demo_key_message_warning(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("PDFREST_API_KEY", VALID_API_KEY)
    caplog.set_level("WARNING", logger="pdfrest.client")

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={**_build_up_response(), "keyMessage": "This is a test key"},
        )

    transport = httpx.MockTransport(handler)
    with PdfRestClient(transport=transport) as client:
        _ = client.up()

    assert "Demo mode restriction message in response" not in caplog.text


@pytest.mark.asyncio
async def test_async_client_raises_for_non_json_success_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PDFREST_API_KEY", ASYNC_API_KEY)

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="not-json")

    transport = httpx.MockTransport(handler)
    async with AsyncPdfRestClient(transport=transport) as client:
        with pytest.raises(
            PdfRestApiError, match="Response body is not valid JSON"
        ) as exc:
            await client.up()
    assert exc.value.status_code == 200
    assert exc.value.response_content == "not-json"


@pytest.mark.asyncio
async def test_async_client_logs_demo_restriction_message_warning(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("PDFREST_API_KEY", ASYNC_API_KEY)
    caplog.set_level("WARNING", logger="pdfrest.client")

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={**_build_up_response(), "message": DEMO_RESTRICTION_MESSAGE},
        )

    transport = httpx.MockTransport(handler)
    async with AsyncPdfRestClient(transport=transport) as client:
        _ = await client.up()

    assert "Demo mode restriction message in response" in caplog.text
    assert "field=message" in caplog.text
    assert DEMO_RESTRICTION_MESSAGE in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field_name", "body_value"),
    [
        pytest.param("message", DEMO_RESTRICTION_MESSAGE, id="message"),
        pytest.param("warning", DEMO_RESTRICTION_MESSAGE, id="warning"),
        pytest.param("keyMessage", DEMO_RESTRICTION_MESSAGE, id="key-message"),
    ],
)
async def test_async_client_logs_demo_restriction_message_warning_all_fields(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    field_name: str,
    body_value: str,
) -> None:
    monkeypatch.setenv("PDFREST_API_KEY", ASYNC_API_KEY)
    caplog.set_level("WARNING", logger="pdfrest.client")

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={**_build_up_response(), field_name: body_value},
        )

    transport = httpx.MockTransport(handler)
    async with AsyncPdfRestClient(transport=transport) as client:
        _ = await client.up()

    assert "Demo mode restriction message in response" in caplog.text
    assert f"field={field_name}" in caplog.text
    assert DEMO_RESTRICTION_MESSAGE in caplog.text


def test_client_uses_text_for_non_json_error_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PDFREST_API_KEY", VALID_API_KEY)

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="server blew up")

    transport = httpx.MockTransport(handler)
    with (
        pytest.raises(PdfRestApiError, match="status code 500") as exc,
        PdfRestClient(transport=transport) as client,
    ):
        client.up()
    assert exc.value.response_content == "server blew up"


@pytest.mark.asyncio
async def test_async_client_uses_text_for_non_json_error_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PDFREST_API_KEY", ASYNC_API_KEY)

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="server blew up")

    transport = httpx.MockTransport(handler)
    async with AsyncPdfRestClient(transport=transport) as client:
        with pytest.raises(PdfRestApiError, match="status code 500") as exc:
            await client.up()
    assert exc.value.response_content == "server blew up"


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


def test_client_preserves_structured_error_detail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PDFREST_API_KEY", VALID_API_KEY)
    error_payload = _build_error_detail_response()

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json=error_payload)

    transport = httpx.MockTransport(handler)
    with (
        pytest.raises(PdfRestApiError, match=r"acceptable range for opacity") as exc,
        PdfRestClient(transport=transport) as client,
    ):
        client.up()

    assert exc.value.status_code == 400
    assert exc.value.response_content == error_payload["errorDetail"]
    assert isinstance(exc.value.response_content, dict)
    issues = exc.value.response_content["issues"]
    assert issues[0]["path"] == "fields.text_objects[0].opacity"
    assert issues[1]["path"] == "fields.text_objects[0].text_color_cmyk[2]"


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
async def test_async_client_preserves_structured_error_detail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PDFREST_API_KEY", ASYNC_API_KEY)
    error_payload = _build_error_detail_response()

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json=error_payload)

    transport = httpx.MockTransport(handler)
    async with AsyncPdfRestClient(transport=transport) as client:
        with pytest.raises(
            PdfRestApiError, match=r"acceptable range for opacity"
        ) as exc:
            await client.up()

    assert exc.value.status_code == 400
    assert exc.value.response_content == error_payload["errorDetail"]
    assert isinstance(exc.value.response_content, dict)
    issues = exc.value.response_content["issues"]
    assert issues[0]["path"] == "fields.text_objects[0].opacity"
    assert issues[1]["path"] == "fields.text_objects[0].text_color_cmyk[2]"


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


def test_stream_upload_does_not_retry_on_429(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PDFREST_API_KEY", VALID_API_KEY)
    monkeypatch.setattr(client_module.random, "uniform", lambda *_: 0.0)
    monkeypatch.setattr(client_module.time, "sleep", lambda _delay: None)

    file_id = _build_file_info()["id"]
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/upload":
            attempts["count"] += 1
            if attempts["count"] == 1:
                return httpx.Response(429, json={"error": "slow"})
            return httpx.Response(200, json={"files": [{"id": file_id}]})
        if request.url.path == f"/resource/{file_id}":
            return httpx.Response(200, json=_build_file_info(file_id))
        msg = f"Unexpected path {request.url.path}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    file_stream = BytesIO(b"payload bytes")
    with (
        pytest.raises(PdfRestApiError, match="slow"),
        PdfRestClient(
            api_key=VALID_API_KEY, transport=transport, max_retries=2
        ) as client,
    ):
        client.files.create([("doc.pdf", file_stream, "application/pdf")])

    assert attempts["count"] == 1


def test_stream_upload_does_not_retry_on_transport_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PDFREST_API_KEY", VALID_API_KEY)
    monkeypatch.setattr(client_module.random, "uniform", lambda *_: 0.0)
    monkeypatch.setattr(client_module.time, "sleep", lambda _delay: None)

    file_id = _build_file_info()["id"]
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/upload":
            attempts["count"] += 1
            if attempts["count"] == 1:
                msg = "boom"
                raise httpx.TransportError(msg)
            return httpx.Response(200, json={"files": [{"id": file_id}]})
        if request.url.path == f"/resource/{file_id}":
            return httpx.Response(200, json=_build_file_info(file_id))
        msg = f"Unexpected path {request.url.path}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    stream = BytesIO(b"payload")
    with (
        pytest.raises(PdfRestTransportError, match="boom"),
        PdfRestClient(
            api_key=VALID_API_KEY, transport=transport, max_retries=2
        ) as client,
    ):
        client.files.create([("doc.pdf", stream, "application/pdf")])

    assert attempts["count"] == 1


def test_stream_upload_retries_on_connect_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PDFREST_API_KEY", VALID_API_KEY)
    monkeypatch.setattr(client_module.random, "uniform", lambda *_: 0.0)
    monkeypatch.setattr(client_module.time, "sleep", lambda _delay: None)

    file_id = _build_file_info()["id"]
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/upload":
            attempts["count"] += 1
            if attempts["count"] == 1:
                msg = "connect timeout"
                raise httpx.ConnectTimeout(msg)
            return httpx.Response(200, json={"files": [{"id": file_id}]})
        if request.url.path == f"/resource/{file_id}":
            return httpx.Response(200, json=_build_file_info(file_id))
        msg = f"Unexpected path {request.url.path}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    stream = BytesIO(b"payload")
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        files = client.files.create([("doc.pdf", stream, "application/pdf")])

    assert attempts["count"] == 2
    assert files[0].id == file_id


def test_stream_upload_retries_on_pool_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PDFREST_API_KEY", VALID_API_KEY)
    monkeypatch.setattr(client_module.random, "uniform", lambda *_: 0.0)
    monkeypatch.setattr(client_module.time, "sleep", lambda _delay: None)

    file_id = _build_file_info()["id"]
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/upload":
            attempts["count"] += 1
            if attempts["count"] == 1:
                msg = "pool timeout"
                raise httpx.PoolTimeout(msg)
            return httpx.Response(200, json={"files": [{"id": file_id}]})
        if request.url.path == f"/resource/{file_id}":
            return httpx.Response(200, json=_build_file_info(file_id))
        msg = f"Unexpected path {request.url.path}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    stream = BytesIO(b"payload")
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        files = client.files.create([("doc.pdf", stream, "application/pdf")])

    assert attempts["count"] == 2
    assert files[0].id == file_id


def test_stream_upload_does_not_retry_on_server_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PDFREST_API_KEY", VALID_API_KEY)
    monkeypatch.setattr(client_module.random, "uniform", lambda *_: 0.0)
    monkeypatch.setattr(client_module.time, "sleep", lambda _delay: None)

    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/upload":
            attempts["count"] += 1
            return httpx.Response(500, json={"error": "retry"})
        msg = f"Unexpected path {request.url.path}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    stream = BytesIO(b"payload")
    with (
        pytest.raises(PdfRestApiError, match="retry"),
        PdfRestClient(
            api_key=VALID_API_KEY, transport=transport, max_retries=2
        ) as client,
    ):
        client.files.create([("doc.pdf", stream, "application/pdf")])

    assert attempts["count"] == 1


def _write_temp_file(tmp_path: Path, content: bytes = b"payload") -> Path:
    path = tmp_path / "doc.pdf"
    path.write_bytes(content)
    return path


def test_create_from_paths_retries_on_429(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("PDFREST_API_KEY", VALID_API_KEY)
    monkeypatch.setattr(client_module.random, "uniform", lambda *_: 0.0)
    monkeypatch.setattr(client_module.time, "sleep", lambda _delay: None)

    upload_path = _write_temp_file(tmp_path)
    file_id = _build_file_info()["id"]
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/upload":
            attempts["count"] += 1
            if attempts["count"] == 1:
                return httpx.Response(429, json={"error": "slow"})
            return httpx.Response(200, json={"files": [{"id": file_id}]})
        if request.url.path == f"/resource/{file_id}":
            return httpx.Response(200, json=_build_file_info(file_id))
        msg = f"Unexpected path {request.url.path}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        files = client.files.create_from_paths(upload_path)

    assert attempts["count"] == 2
    assert len(files) == 1
    assert files[0].id == file_id


def test_create_from_paths_retries_on_transport_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("PDFREST_API_KEY", VALID_API_KEY)
    monkeypatch.setattr(client_module.random, "uniform", lambda *_: 0.0)
    monkeypatch.setattr(client_module.time, "sleep", lambda _delay: None)

    upload_path = _write_temp_file(tmp_path)
    file_id = _build_file_info()["id"]
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/upload":
            attempts["count"] += 1
            if attempts["count"] == 1:
                msg = "boom"
                raise httpx.TransportError(msg)
            return httpx.Response(200, json={"files": [{"id": file_id}]})
        if request.url.path == f"/resource/{file_id}":
            return httpx.Response(200, json=_build_file_info(file_id))
        msg = f"Unexpected path {request.url.path}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        files = client.files.create_from_paths(upload_path)

    assert attempts["count"] == 2
    assert len(files) == 1
    assert files[0].id == file_id


def test_create_from_paths_retries_on_connect_timeout(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("PDFREST_API_KEY", VALID_API_KEY)
    monkeypatch.setattr(client_module.random, "uniform", lambda *_: 0.0)
    monkeypatch.setattr(client_module.time, "sleep", lambda _delay: None)

    upload_path = _write_temp_file(tmp_path)
    file_id = _build_file_info()["id"]
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/upload":
            attempts["count"] += 1
            if attempts["count"] == 1:
                msg = "connect timeout"
                raise httpx.ConnectTimeout(msg)
            return httpx.Response(200, json={"files": [{"id": file_id}]})
        if request.url.path == f"/resource/{file_id}":
            return httpx.Response(200, json=_build_file_info(file_id))
        msg = f"Unexpected path {request.url.path}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        files = client.files.create_from_paths(upload_path)

    assert attempts["count"] == 2
    assert len(files) == 1
    assert files[0].id == file_id


def test_create_from_paths_retries_on_pool_timeout(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("PDFREST_API_KEY", VALID_API_KEY)
    monkeypatch.setattr(client_module.random, "uniform", lambda *_: 0.0)
    monkeypatch.setattr(client_module.time, "sleep", lambda _delay: None)

    upload_path = _write_temp_file(tmp_path)
    file_id = _build_file_info()["id"]
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/upload":
            attempts["count"] += 1
            if attempts["count"] == 1:
                msg = "pool timeout"
                raise httpx.PoolTimeout(msg)
            return httpx.Response(200, json={"files": [{"id": file_id}]})
        if request.url.path == f"/resource/{file_id}":
            return httpx.Response(200, json=_build_file_info(file_id))
        msg = f"Unexpected path {request.url.path}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        files = client.files.create_from_paths(upload_path)

    assert attempts["count"] == 2
    assert len(files) == 1
    assert files[0].id == file_id


def test_stream_upload_does_not_retry_on_read_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PDFREST_API_KEY", VALID_API_KEY)
    monkeypatch.setattr(client_module.random, "uniform", lambda *_: 0.0)
    monkeypatch.setattr(client_module.time, "sleep", lambda _delay: None)

    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/upload":
            attempts["count"] += 1
            if attempts["count"] == 1:
                msg = "read timeout"
                raise httpx.ReadTimeout(msg)
            return httpx.Response(200, json={"files": []})
        msg = f"Unexpected path {request.url.path}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    stream = BytesIO(b"payload")
    with (
        pytest.raises(PdfRestTimeoutError, match="timeout"),
        PdfRestClient(
            api_key=VALID_API_KEY, transport=transport, max_retries=2
        ) as client,
    ):
        client.files.create([("doc.pdf", stream, "application/pdf")])

    assert attempts["count"] == 1


def test_client_retry_fails_for_non_seekable_stream(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PDFREST_API_KEY", VALID_API_KEY)
    monkeypatch.setattr(client_module.random, "uniform", lambda *_: 0.0)
    monkeypatch.setattr(client_module.time, "sleep", lambda _delay: None)

    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/upload":
            attempts["count"] += 1
            return httpx.Response(500, json={"error": "retry"})
        msg = f"Unexpected path {request.url.path}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    stream = NonSeekableByteStream(b"payload")
    with (
        pytest.raises(PdfRestApiError, match="retry"),
        PdfRestClient(
            api_key=VALID_API_KEY, transport=transport, max_retries=1
        ) as client,
    ):
        client.files.create([("doc.pdf", stream, "application/pdf")])

    assert attempts["count"] == 1


@pytest.mark.asyncio
async def test_async_stream_upload_retries_on_429(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PDFREST_API_KEY", ASYNC_API_KEY)
    monkeypatch.setattr(client_module.random, "uniform", lambda *_: 0.0)

    async def fake_sleep(_delay: float) -> None:
        return None

    monkeypatch.setattr(client_module.asyncio, "sleep", fake_sleep)

    file_id = _build_file_info()["id"]
    attempts = {"count": 0}

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/upload":
            attempts["count"] += 1
            if attempts["count"] == 1:
                return httpx.Response(429, json={"error": "slow"})
            return httpx.Response(200, json={"files": [{"id": file_id}]})
        if request.url.path == f"/resource/{file_id}":
            return httpx.Response(200, json=_build_file_info(file_id))
        msg = f"Unexpected path {request.url.path}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    stream = BytesIO(b"async payload")
    with pytest.raises(PdfRestApiError, match="slow"):
        async with AsyncPdfRestClient(
            api_key=ASYNC_API_KEY, transport=transport, max_retries=2
        ) as client:
            await client.files.create([("doc.pdf", stream, "application/pdf")])

    assert attempts["count"] == 1


@pytest.mark.asyncio
async def test_async_stream_upload_does_not_retry_on_transport_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PDFREST_API_KEY", ASYNC_API_KEY)
    monkeypatch.setattr(client_module.random, "uniform", lambda *_: 0.0)

    async def fake_sleep(_delay: float) -> None:
        return None

    monkeypatch.setattr(client_module.asyncio, "sleep", fake_sleep)

    file_id = _build_file_info()["id"]
    attempts = {"count": 0}

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/upload":
            attempts["count"] += 1
            if attempts["count"] == 1:
                msg = "boom"
                raise httpx.TransportError(msg)
            return httpx.Response(200, json={"files": [{"id": file_id}]})
        if request.url.path == f"/resource/{file_id}":
            return httpx.Response(200, json=_build_file_info(file_id))
        msg = f"Unexpected path {request.url.path}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    stream = BytesIO(b"async payload")
    with pytest.raises(PdfRestTransportError, match="boom"):
        async with AsyncPdfRestClient(
            api_key=ASYNC_API_KEY, transport=transport, max_retries=2
        ) as client:
            await client.files.create([("doc.pdf", stream, "application/pdf")])

    assert attempts["count"] == 1


@pytest.mark.asyncio
async def test_async_stream_upload_retries_on_connect_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PDFREST_API_KEY", ASYNC_API_KEY)
    monkeypatch.setattr(client_module.random, "uniform", lambda *_: 0.0)

    async def fake_sleep(_delay: float) -> None:
        return None

    monkeypatch.setattr(client_module.asyncio, "sleep", fake_sleep)

    file_id = _build_file_info()["id"]
    attempts = {"count": 0}

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/upload":
            attempts["count"] += 1
            if attempts["count"] == 1:
                msg = "connect timeout"
                raise httpx.ConnectTimeout(msg)
            return httpx.Response(200, json={"files": [{"id": file_id}]})
        if request.url.path == f"/resource/{file_id}":
            return httpx.Response(200, json=_build_file_info(file_id))
        msg = f"Unexpected path {request.url.path}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    stream = BytesIO(b"async payload")
    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        files = await client.files.create([("doc.pdf", stream, "application/pdf")])

    assert attempts["count"] == 2
    assert len(files) == 1
    assert files[0].id == file_id


@pytest.mark.asyncio
async def test_async_stream_upload_retries_on_pool_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PDFREST_API_KEY", ASYNC_API_KEY)
    monkeypatch.setattr(client_module.random, "uniform", lambda *_: 0.0)

    async def fake_sleep(_delay: float) -> None:
        return None

    monkeypatch.setattr(client_module.asyncio, "sleep", fake_sleep)

    file_id = _build_file_info()["id"]
    attempts = {"count": 0}

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/upload":
            attempts["count"] += 1
            if attempts["count"] == 1:
                msg = "pool timeout"
                raise httpx.PoolTimeout(msg)
            return httpx.Response(200, json={"files": [{"id": file_id}]})
        if request.url.path == f"/resource/{file_id}":
            return httpx.Response(200, json=_build_file_info(file_id))
        msg = f"Unexpected path {request.url.path}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    stream = BytesIO(b"async payload")
    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        files = await client.files.create([("doc.pdf", stream, "application/pdf")])

    assert attempts["count"] == 2
    assert len(files) == 1
    assert files[0].id == file_id


@pytest.mark.asyncio
async def test_async_stream_upload_does_not_retry_on_read_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PDFREST_API_KEY", ASYNC_API_KEY)
    monkeypatch.setattr(client_module.random, "uniform", lambda *_: 0.0)

    async def fake_sleep(_delay: float) -> None:
        return None

    monkeypatch.setattr(client_module.asyncio, "sleep", fake_sleep)

    attempts = {"count": 0}

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/upload":
            attempts["count"] += 1
            if attempts["count"] == 1:
                msg = "read timeout"
                raise httpx.ReadTimeout(msg)
            return httpx.Response(200, json={"files": []})
        msg = f"Unexpected path {request.url.path}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    stream = BytesIO(b"async payload")
    with pytest.raises(PdfRestTimeoutError, match="timeout"):
        async with AsyncPdfRestClient(
            api_key=ASYNC_API_KEY,
            transport=transport,
            max_retries=2,
        ) as client:
            await client.files.create([("doc.pdf", stream, "application/pdf")])

    assert attempts["count"] == 1


@pytest.mark.asyncio
async def test_async_retry_fails_for_non_seekable_stream(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PDFREST_API_KEY", ASYNC_API_KEY)
    monkeypatch.setattr(client_module.random, "uniform", lambda *_: 0.0)

    async def fake_sleep(_delay: float) -> None:
        return None

    monkeypatch.setattr(client_module.asyncio, "sleep", fake_sleep)

    attempts = {"count": 0}

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/upload":
            attempts["count"] += 1
            return httpx.Response(500, json={"error": "retry"})
        msg = f"Unexpected path {request.url.path}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    stream = NonSeekableByteStream(b"payload")
    with pytest.raises(PdfRestApiError, match="retry"):
        async with AsyncPdfRestClient(
            api_key=ASYNC_API_KEY,
            transport=transport,
            max_retries=1,
        ) as client:
            await client.files.create([("doc.pdf", stream, "application/pdf")])

    assert attempts["count"] == 1


@pytest.mark.asyncio
async def test_async_create_from_paths_retries_on_429(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("PDFREST_API_KEY", ASYNC_API_KEY)
    monkeypatch.setattr(client_module.random, "uniform", lambda *_: 0.0)

    upload_path = _write_temp_file(tmp_path)
    file_id = _build_file_info()["id"]
    attempts = {"count": 0}

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/upload":
            attempts["count"] += 1
            if attempts["count"] == 1:
                return httpx.Response(429, json={"error": "slow"})
            return httpx.Response(200, json={"files": [{"id": file_id}]})
        if request.url.path == f"/resource/{file_id}":
            return httpx.Response(200, json=_build_file_info(file_id))
        msg = f"Unexpected path {request.url.path}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        files = await client.files.create_from_paths(upload_path)

    assert attempts["count"] == 2
    assert len(files) == 1
    assert files[0].id == file_id


@pytest.mark.asyncio
async def test_async_create_from_paths_retries_on_transport_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("PDFREST_API_KEY", ASYNC_API_KEY)
    monkeypatch.setattr(client_module.random, "uniform", lambda *_: 0.0)

    upload_path = _write_temp_file(tmp_path)
    file_id = _build_file_info()["id"]
    attempts = {"count": 0}

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/upload":
            attempts["count"] += 1
            if attempts["count"] == 1:
                msg = "boom"
                raise httpx.TransportError(msg)
            return httpx.Response(200, json={"files": [{"id": file_id}]})
        if request.url.path == f"/resource/{file_id}":
            return httpx.Response(200, json=_build_file_info(file_id))
        msg = f"Unexpected path {request.url.path}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        files = await client.files.create_from_paths(upload_path)

    assert attempts["count"] == 2
    assert len(files) == 1
    assert files[0].id == file_id


@pytest.mark.asyncio
async def test_async_create_from_paths_retries_on_connect_timeout(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("PDFREST_API_KEY", ASYNC_API_KEY)
    monkeypatch.setattr(client_module.random, "uniform", lambda *_: 0.0)

    upload_path = _write_temp_file(tmp_path)
    file_id = _build_file_info()["id"]
    attempts = {"count": 0}

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/upload":
            attempts["count"] += 1
            if attempts["count"] == 1:
                msg = "connect timeout"
                raise httpx.ConnectTimeout(msg)
            return httpx.Response(200, json={"files": [{"id": file_id}]})
        if request.url.path == f"/resource/{file_id}":
            return httpx.Response(200, json=_build_file_info(file_id))
        msg = f"Unexpected path {request.url.path}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        files = await client.files.create_from_paths(upload_path)

    assert attempts["count"] == 2
    assert len(files) == 1
    assert files[0].id == file_id


@pytest.mark.asyncio
async def test_async_create_from_paths_retries_on_pool_timeout(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("PDFREST_API_KEY", ASYNC_API_KEY)
    monkeypatch.setattr(client_module.random, "uniform", lambda *_: 0.0)

    upload_path = _write_temp_file(tmp_path)
    file_id = _build_file_info()["id"]
    attempts = {"count": 0}

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/upload":
            attempts["count"] += 1
            if attempts["count"] == 1:
                msg = "pool timeout"
                raise httpx.PoolTimeout(msg)
            return httpx.Response(200, json={"files": [{"id": file_id}]})
        if request.url.path == f"/resource/{file_id}":
            return httpx.Response(200, json=_build_file_info(file_id))
        msg = f"Unexpected path {request.url.path}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        files = await client.files.create_from_paths(upload_path)

    assert attempts["count"] == 2
    assert len(files) == 1
    assert files[0].id == file_id


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
