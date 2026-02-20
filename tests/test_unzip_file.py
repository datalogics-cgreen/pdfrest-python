from __future__ import annotations

import json
import logging

import httpx
import pytest
from pydantic import ValidationError

from pdfrest import AsyncPdfRestClient, PdfRestClient
from pdfrest.models import PdfRestFile, PdfRestFileBasedResponse, PdfRestFileID
from pdfrest.models._internal import UnzipPayload

from .graphics_test_helpers import (
    ASYNC_API_KEY,
    VALID_API_KEY,
    build_file_info_payload,
)

DEMO_REPLACEMENT_ID = "00000000-0000-4000-8000-000000000000"


def make_zip_file(file_id: str, name: str = "archive.zip") -> PdfRestFile:
    return PdfRestFile.model_validate(
        build_file_info_payload(file_id, name, "application/zip")
    )


def test_unzip_file_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    zip_file = make_zip_file(str(PdfRestFileID.generate()))
    output_id = str(PdfRestFileID.generate())

    payload_dump = UnzipPayload.model_validate({"files": zip_file}).model_dump(
        mode="json", by_alias=True, exclude_none=True, exclude_unset=True
    )

    seen: dict[str, int] = {"post": 0, "get": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/unzip":
            seen["post"] += 1
            payload = json.loads(request.content.decode("utf-8"))
            assert payload == payload_dump
            return httpx.Response(
                200,
                json={
                    "inputId": [zip_file.id],
                    "files": [
                        {
                            "name": "inner.txt",
                            "id": output_id,
                            "outputUrl": f"https://api.pdfrest.com/resource/{output_id}",
                        }
                    ],
                },
            )
        if request.method == "GET" and request.url.path == f"/resource/{output_id}":
            seen["get"] += 1
            assert request.url.params["format"] == "info"
            return httpx.Response(
                200,
                json=build_file_info_payload(
                    output_id,
                    "inner.txt",
                    "text/plain",
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.unzip_file(zip_file)

    assert seen == {"post": 1, "get": 1}
    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.output_file.name == "inner.txt"
    assert response.output_file.type == "text/plain"
    assert str(response.input_id) == str(zip_file.id)


def test_unzip_file_with_password_and_customization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    zip_file = make_zip_file(str(PdfRestFileID.generate()))
    output_id = str(PdfRestFileID.generate())
    captured_timeout: dict[str, float | dict[str, float] | None] = {}

    password = "Secret123"  # noqa: S105 - test-only password fixture

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/unzip":
            assert request.url.params["trace"] == "sync"
            assert request.headers["X-Debug"] == "sync"
            captured_timeout["value"] = request.extensions.get("timeout")
            payload = json.loads(request.content.decode("utf-8"))
            assert payload["id"] == str(zip_file.id)
            assert payload["password"] == password
            assert payload["diagnostics"] == "on"
            return httpx.Response(
                200,
                json={
                    "inputId": [zip_file.id],
                    "outputId": [output_id],
                },
            )
        if request.method == "GET" and request.url.path == f"/resource/{output_id}":
            assert request.url.params["trace"] == "sync"
            assert request.headers["X-Debug"] == "sync"
            return httpx.Response(
                200,
                json=build_file_info_payload(
                    output_id,
                    "custom-unzip.txt",
                    "text/plain",
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.unzip_file(
            zip_file,
            password=password,
            extra_query={"trace": "sync"},
            extra_headers={"X-Debug": "sync"},
            extra_body={"diagnostics": "on"},
            timeout=0.25,
        )

    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.output_file.name == "custom-unzip.txt"
    timeout_value = captured_timeout["value"]
    assert timeout_value is not None
    if isinstance(timeout_value, dict):
        assert all(pytest.approx(0.25) == value for value in timeout_value.values())
    else:
        assert timeout_value == pytest.approx(0.25)


def test_unzip_file_requires_zip(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    non_zip = PdfRestFile.model_validate(
        build_file_info_payload(
            str(PdfRestFileID.generate()), "document.pdf", "application/pdf"
        )
    )
    transport = httpx.MockTransport(lambda request: (_ for _ in ()).throw(RuntimeError))

    with (
        PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client,
        pytest.raises(ValidationError, match="Must be a ZIP file"),
    ):
        client.unzip_file(non_zip)


def test_unzip_file_single_input(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    first = make_zip_file(str(PdfRestFileID.generate()))
    second = make_zip_file(str(PdfRestFileID.generate()))
    transport = httpx.MockTransport(lambda request: (_ for _ in ()).throw(RuntimeError))

    with (
        PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client,
        pytest.raises(ValidationError, match="at most 1 item"),
    ):
        client.unzip_file([first, second])


@pytest.mark.asyncio
async def test_async_unzip_file(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    zip_file = make_zip_file(str(PdfRestFileID.generate()))
    output_id = str(PdfRestFileID.generate())

    payload_dump = UnzipPayload.model_validate({"files": zip_file}).model_dump(
        mode="json", by_alias=True, exclude_none=True, exclude_unset=True
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/unzip":
            payload = json.loads(request.content.decode("utf-8"))
            assert payload == payload_dump
            return httpx.Response(
                200,
                json={
                    "inputId": [zip_file.id],
                    "files": [
                        {
                            "name": "async.txt",
                            "id": output_id,
                            "outputUrl": f"https://api.pdfrest.com/resource/{output_id}",
                        }
                    ],
                },
            )
        if request.method == "GET" and request.url.path == f"/resource/{output_id}":
            return httpx.Response(
                200,
                json=build_file_info_payload(
                    output_id,
                    "async.txt",
                    "text/plain",
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        response = await client.unzip_file(zip_file)

    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.output_file.name == "async.txt"
    assert str(response.input_id) == str(zip_file.id)


@pytest.mark.asyncio
async def test_async_unzip_file_with_password_and_customization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    zip_file = make_zip_file(str(PdfRestFileID.generate()))
    output_id = str(PdfRestFileID.generate())
    captured_timeout: dict[str, float | dict[str, float] | None] = {}

    password = "Secret123"  # noqa: S105 - test-only password fixture

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/unzip":
            assert request.url.params["trace"] == "async"
            assert request.headers["X-Debug"] == "async"
            captured_timeout["value"] = request.extensions.get("timeout")
            payload = json.loads(request.content.decode("utf-8"))
            assert payload["id"] == str(zip_file.id)
            assert payload["password"] == password
            assert payload["diagnostics"] == "on"
            return httpx.Response(
                200,
                json={
                    "inputId": [zip_file.id],
                    "outputId": [output_id],
                },
            )
        if request.method == "GET" and request.url.path == f"/resource/{output_id}":
            assert request.url.params["trace"] == "async"
            assert request.headers["X-Debug"] == "async"
            return httpx.Response(
                200,
                json=build_file_info_payload(
                    output_id,
                    "async-custom-unzip.txt",
                    "text/plain",
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        response = await client.unzip_file(
            zip_file,
            password=password,
            extra_query={"trace": "async"},
            extra_headers={"X-Debug": "async"},
            extra_body={"diagnostics": "on"},
            timeout=0.25,
        )

    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.output_file.name == "async-custom-unzip.txt"
    timeout_value = captured_timeout["value"]
    assert timeout_value is not None
    if isinstance(timeout_value, dict):
        assert all(pytest.approx(0.25) == value for value in timeout_value.values())
    else:
        assert timeout_value == pytest.approx(0.25)


@pytest.mark.asyncio
async def test_async_unzip_file_requires_zip(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    non_zip = PdfRestFile.model_validate(
        build_file_info_payload(
            str(PdfRestFileID.generate()), "document.pdf", "application/pdf"
        )
    )
    transport = httpx.MockTransport(lambda request: (_ for _ in ()).throw(RuntimeError))

    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        with pytest.raises(ValidationError, match="Must be a ZIP file"):
            await client.unzip_file(non_zip)


@pytest.mark.asyncio
async def test_async_unzip_file_single_input(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    first = make_zip_file(str(PdfRestFileID.generate()))
    second = make_zip_file(str(PdfRestFileID.generate()))
    transport = httpx.MockTransport(lambda request: (_ for _ in ()).throw(RuntimeError))

    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        with pytest.raises(ValidationError, match="at most 1 item"):
            await client.unzip_file([first, second])


def test_unzip_file_demo_redacted_id_replaced_and_logged(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    caplog.set_level(logging.WARNING, logger="pdfrest.models")
    zip_file = make_zip_file(str(PdfRestFileID.generate()))
    redacted_id = "XXXXXXXXX-XXXXXXXXX-XXXX-XXXXXXXXXXXX"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/unzip":
            return httpx.Response(
                200,
                json={
                    "inputId": [zip_file.id],
                    "files": [
                        {
                            "name": "inner.txt",
                            "id": redacted_id,
                            "outputUrl": (
                                "https://api.pdfrest.com/resource/"
                                f"{redacted_id}?format=file"
                            ),
                        }
                    ],
                },
            )
        if (
            request.method == "GET"
            and request.url.path == f"/resource/{DEMO_REPLACEMENT_ID}"
        ):
            return httpx.Response(
                200,
                json=build_file_info_payload(
                    DEMO_REPLACEMENT_ID,
                    "inner.txt",
                    "text/plain",
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.unzip_file(zip_file)

    assert response.output_file.id == DEMO_REPLACEMENT_ID
    assert (
        "Demo value XXXXXXXXX-XXXXXXXXX-XXXX-XXXXXXXXXXXX detected in id; "
        "replaced with 00000000-0000-4000-8000-000000000000" in caplog.text
    )


def test_unzip_file_demo_fallback_file_info_on_404(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    caplog.set_level(logging.WARNING, logger="pdfrest.client")
    zip_file = make_zip_file(str(PdfRestFileID.generate()))

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/unzip":
            return httpx.Response(
                200,
                json={
                    "inputId": [zip_file.id],
                    "files": [
                        {
                            "name": "inner.txt",
                            "id": DEMO_REPLACEMENT_ID,
                            "outputUrl": None,
                        }
                    ],
                },
            )
        if (
            request.method == "GET"
            and request.url.path == f"/resource/{DEMO_REPLACEMENT_ID}"
        ):
            return httpx.Response(404, json={"error": "The file does not exist."})
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.unzip_file(zip_file)

    assert response.output_file.id == DEMO_REPLACEMENT_ID
    assert response.output_file.name == "demo-redacted.bin"
    assert str(response.output_file.url) == "https://pdfrest.com/demo-redacted"
    assert response.output_file.type == "application/octet-stream"
    assert response.output_file.size == 1
    assert (
        "Demo fallback file id 00000000-0000-4000-8000-000000000000 was not found "
        "during file-info lookup; returning placeholder metadata." in caplog.text
    )


@pytest.mark.asyncio
async def test_async_unzip_file_demo_fallback_file_info_on_404(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    caplog.set_level(logging.WARNING, logger="pdfrest.client")
    zip_file = make_zip_file(str(PdfRestFileID.generate()))

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/unzip":
            return httpx.Response(
                200,
                json={
                    "inputId": [zip_file.id],
                    "files": [
                        {
                            "name": "inner-async.txt",
                            "id": DEMO_REPLACEMENT_ID,
                            "outputUrl": None,
                        }
                    ],
                },
            )
        if (
            request.method == "GET"
            and request.url.path == f"/resource/{DEMO_REPLACEMENT_ID}"
        ):
            return httpx.Response(404, json={"error": "The file does not exist."})
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        response = await client.unzip_file(zip_file)

    assert response.output_file.id == DEMO_REPLACEMENT_ID
    assert response.output_file.name == "demo-redacted.bin"
    assert str(response.output_file.url) == "https://pdfrest.com/demo-redacted"
    assert response.output_file.type == "application/octet-stream"
    assert response.output_file.size == 1
    assert (
        "Demo fallback file id 00000000-0000-4000-8000-000000000000 was not found "
        "during file-info lookup; returning placeholder metadata." in caplog.text
    )
