from __future__ import annotations

import json

import httpx
import pytest
from pydantic import ValidationError

from pdfrest import AsyncPdfRestClient, PdfRestClient
from pdfrest.models import PdfRestFile, PdfRestFileBasedResponse, PdfRestFileID
from pdfrest.models._internal import PdfLinearizePayload

from .graphics_test_helpers import (
    ASYNC_API_KEY,
    VALID_API_KEY,
    build_file_info_payload,
    make_pdf_file,
)


def test_linearize_pdf_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(1))
    output_id = str(PdfRestFileID.generate())

    payload_dump = PdfLinearizePayload.model_validate(
        {"files": [input_file]}
    ).model_dump(mode="json", by_alias=True, exclude_none=True, exclude_unset=True)

    seen: dict[str, int] = {"post": 0, "get": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/linearized-pdf":
            seen["post"] += 1
            payload = json.loads(request.content.decode("utf-8"))
            assert payload == payload_dump
            return httpx.Response(
                200,
                json={
                    "inputId": [input_file.id],
                    "outputId": [output_id],
                },
            )
        if request.method == "GET" and request.url.path == f"/resource/{output_id}":
            seen["get"] += 1
            assert request.url.params["format"] == "info"
            return httpx.Response(
                200,
                json=build_file_info_payload(
                    output_id,
                    "linearized.pdf",
                    "application/pdf",
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.linearize_pdf(input_file)

    assert seen == {"post": 1, "get": 1}
    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.output_file.name == "linearized.pdf"
    assert response.output_file.type == "application/pdf"
    assert str(response.input_id) == str(input_file.id)
    assert response.warning is None


def test_linearize_pdf_request_customization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(1))
    output_id = str(PdfRestFileID.generate())
    captured_timeout: dict[str, float | dict[str, float] | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/linearized-pdf":
            assert request.url.params["trace"] == "true"
            assert request.headers["X-Debug"] == "sync"
            captured_timeout["value"] = request.extensions.get("timeout")
            payload = json.loads(request.content.decode("utf-8"))
            assert payload["debug"] == "yes"
            assert payload["id"] == str(input_file.id)
            assert payload["output"] == "linearized"
            return httpx.Response(
                200,
                json={
                    "inputId": [input_file.id],
                    "outputId": [output_id],
                },
            )
        if request.method == "GET" and request.url.path == f"/resource/{output_id}":
            assert request.url.params["format"] == "info"
            assert request.url.params["trace"] == "true"
            assert request.headers["X-Debug"] == "sync"
            return httpx.Response(
                200,
                json=build_file_info_payload(
                    output_id,
                    "linearized-out.pdf",
                    "application/pdf",
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.linearize_pdf(
            input_file,
            output="linearized",
            extra_query={"trace": "true"},
            extra_headers={"X-Debug": "sync"},
            extra_body={"debug": "yes"},
            timeout=0.61,
        )

    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.output_file.name == "linearized-out.pdf"
    timeout_value = captured_timeout["value"]
    assert timeout_value is not None
    if isinstance(timeout_value, dict):
        assert all(
            component == pytest.approx(0.61) for component in timeout_value.values()
        )
    else:
        assert timeout_value == pytest.approx(0.61)


@pytest.mark.asyncio
async def test_async_linearize_pdf_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(2))
    output_id = str(PdfRestFileID.generate())

    payload_dump = PdfLinearizePayload.model_validate(
        {"files": [input_file]}
    ).model_dump(mode="json", by_alias=True, exclude_none=True, exclude_unset=True)

    seen: dict[str, int] = {"post": 0, "get": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/linearized-pdf":
            seen["post"] += 1
            payload = json.loads(request.content.decode("utf-8"))
            assert payload == payload_dump
            return httpx.Response(
                200,
                json={
                    "inputId": [input_file.id],
                    "outputId": [output_id],
                },
            )
        if request.method == "GET" and request.url.path == f"/resource/{output_id}":
            seen["get"] += 1
            assert request.url.params["format"] == "info"
            return httpx.Response(
                200,
                json=build_file_info_payload(
                    output_id,
                    "async-linearized.pdf",
                    "application/pdf",
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        response = await client.linearize_pdf(input_file)

    assert seen == {"post": 1, "get": 1}
    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.output_file.name == "async-linearized.pdf"
    assert response.output_file.type == "application/pdf"
    assert str(response.input_id) == str(input_file.id)


@pytest.mark.asyncio
async def test_async_linearize_pdf_request_customization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(2))
    output_id = str(PdfRestFileID.generate())
    captured_timeout: dict[str, float | dict[str, float] | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/linearized-pdf":
            assert request.url.params["trace"] == "async"
            assert request.headers["X-Debug"] == "async"
            captured_timeout["value"] = request.extensions.get("timeout")
            payload = json.loads(request.content.decode("utf-8"))
            assert payload["flags"] == ["a", "b"]
            assert payload["id"] == str(input_file.id)
            return httpx.Response(
                200,
                json={
                    "inputId": [input_file.id],
                    "outputId": [output_id],
                },
            )
        if request.method == "GET" and request.url.path == f"/resource/{output_id}":
            assert request.url.params["format"] == "info"
            assert request.url.params["trace"] == "async"
            assert request.headers["X-Debug"] == "async"
            return httpx.Response(
                200,
                json=build_file_info_payload(
                    output_id,
                    "async-linearized-custom.pdf",
                    "application/pdf",
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        response = await client.linearize_pdf(
            input_file,
            extra_query={"trace": "async"},
            extra_headers={"X-Debug": "async"},
            extra_body={"flags": ["a", "b"]},
            timeout=0.83,
        )

    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.output_file.name == "async-linearized-custom.pdf"
    timeout_value = captured_timeout["value"]
    assert timeout_value is not None
    if isinstance(timeout_value, dict):
        assert all(
            component == pytest.approx(0.83) for component in timeout_value.values()
        )
    else:
        assert timeout_value == pytest.approx(0.83)


@pytest.mark.parametrize(
    ("files", "match"),
    [
        pytest.param(
            "png",
            "Must be a PDF file",
            id="non-pdf-file",
        ),
        pytest.param(
            "multiple",
            "List should have at most 1 item after validation",
            id="multiple-files",
        ),
    ],
)
def test_linearize_pdf_validation(
    monkeypatch: pytest.MonkeyPatch,
    files: str,
    match: str,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    pdf_file = make_pdf_file(PdfRestFileID.generate(1))
    png_file = PdfRestFile.model_validate(
        build_file_info_payload(
            PdfRestFileID.generate(),
            "example.png",
            "image/png",
        )
    )
    transport = httpx.MockTransport(lambda request: (_ for _ in ()).throw(RuntimeError))
    files_argument = (
        png_file
        if files == "png"
        else [pdf_file, make_pdf_file(PdfRestFileID.generate())]
    )

    with (
        PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client,
        pytest.raises(ValidationError, match=match),
    ):
        client.linearize_pdf(files_argument)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("files", "match"),
    [
        pytest.param(
            "png",
            "Must be a PDF file",
            id="non-pdf-file",
        ),
        pytest.param(
            "multiple",
            "List should have at most 1 item after validation",
            id="multiple-files",
        ),
    ],
)
async def test_async_linearize_pdf_validation(
    monkeypatch: pytest.MonkeyPatch,
    files: str,
    match: str,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    pdf_file = make_pdf_file(PdfRestFileID.generate(1))
    png_file = PdfRestFile.model_validate(
        build_file_info_payload(
            PdfRestFileID.generate(),
            "example.png",
            "image/png",
        )
    )
    transport = httpx.MockTransport(lambda request: (_ for _ in ()).throw(RuntimeError))
    files_argument = (
        png_file
        if files == "png"
        else [pdf_file, make_pdf_file(PdfRestFileID.generate())]
    )

    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        with pytest.raises(ValidationError, match=match):
            await client.linearize_pdf(files_argument)
