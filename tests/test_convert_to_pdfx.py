from __future__ import annotations

import json

import httpx
import pytest
from pydantic import ValidationError

from pdfrest import AsyncPdfRestClient, PdfRestClient
from pdfrest.models import PdfRestFile, PdfRestFileBasedResponse, PdfRestFileID
from pdfrest.models._internal import PdfToPdfxPayload
from pdfrest.types import PdfXType

from .graphics_test_helpers import (
    ASYNC_API_KEY,
    VALID_API_KEY,
    build_file_info_payload,
    make_pdf_file,
)


def test_convert_to_pdfx_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(1))
    output_id = str(PdfRestFileID.generate())
    output_type: PdfXType = "PDF/X-4"

    payload_dump = PdfToPdfxPayload.model_validate(
        {"files": [input_file], "output_type": output_type, "output": "print-ready"}
    ).model_dump(mode="json", by_alias=True, exclude_none=True, exclude_unset=True)

    seen: dict[str, int] = {"post": 0, "get": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/pdfx":
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
                    output_id, "print-ready.pdf", "application/pdf"
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.convert_to_pdfx(
            input_file,
            output_type=output_type,
            output="print-ready",
        )

    assert seen == {"post": 1, "get": 1}
    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.output_file.name == "print-ready.pdf"
    assert response.output_file.type == "application/pdf"
    assert str(response.input_id) == str(input_file.id)
    assert response.warning is None


@pytest.mark.asyncio
async def test_async_convert_to_pdfx_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(2))
    output_id = str(PdfRestFileID.generate())
    output_type: PdfXType = "PDF/X-1a"

    payload_dump = PdfToPdfxPayload.model_validate(
        {"files": [input_file], "output_type": output_type}
    ).model_dump(mode="json", by_alias=True, exclude_none=True, exclude_unset=True)

    seen: dict[str, int] = {"post": 0, "get": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/pdfx":
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
                json=build_file_info_payload(output_id, "async.pdf", "application/pdf"),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        response = await client.convert_to_pdfx(
            input_file,
            output_type=output_type,
        )

    assert seen == {"post": 1, "get": 1}
    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.output_file.name == "async.pdf"
    assert response.output_file.type == "application/pdf"
    assert str(response.input_id) == str(input_file.id)


def test_convert_to_pdfx_validation(monkeypatch: pytest.MonkeyPatch) -> None:
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

    with (
        PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client,
        pytest.raises(
            ValidationError,
            match="Input should be 'PDF/X-1a', 'PDF/X-3', 'PDF/X-4' or 'PDF/X-6'",
        ),
    ):
        client.convert_to_pdfx(pdf_file, output_type=None)  # type: ignore[arg-type]

    with (
        PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client,
        pytest.raises(ValidationError, match="Must be a PDF file"),
    ):
        client.convert_to_pdfx(png_file, output_type="PDF/X-3")

    with (
        PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client,
        pytest.raises(ValidationError, match="PDF/X-1a"),
    ):
        client.convert_to_pdfx(pdf_file, output_type="PDF/X-5")  # type: ignore[arg-type]
