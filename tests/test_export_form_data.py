from __future__ import annotations

import json

import httpx
import pytest
from pydantic import ValidationError

from pdfrest import AsyncPdfRestClient, PdfRestClient
from pdfrest.models import PdfRestFile, PdfRestFileBasedResponse, PdfRestFileID
from pdfrest.models._internal import PdfExportFormDataPayload
from pdfrest.types import ExportDataFormat

from .graphics_test_helpers import (
    ASYNC_API_KEY,
    VALID_API_KEY,
    build_file_info_payload,
    make_pdf_file,
)


@pytest.mark.parametrize(
    ("data_format", "output_name", "mime_type"),
    [
        pytest.param("fdf", "exported-data.fdf", "application/vnd.fdf", id="fdf"),
        pytest.param(
            "xfdf",
            "exported-data.xfdf",
            "application/vnd.adobe.xfdf",
            id="xfdf",
        ),
        pytest.param("xml", "exported-data.xml", "application/xml", id="xml"),
        pytest.param(
            "xdp",
            "exported-data.xdp",
            "application/vnd.adobe.xdp+xml",
            id="xdp",
        ),
        pytest.param(
            "xfd",
            "exported-data.xfd",
            "application/vnd.adobe.xfd+xml",
            id="xfd",
        ),
    ],
)
def test_export_form_data_success(
    monkeypatch: pytest.MonkeyPatch,
    data_format: ExportDataFormat,
    output_name: str,
    mime_type: str,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(1))
    output_id = str(PdfRestFileID.generate())

    payload_dump = PdfExportFormDataPayload.model_validate(
        {"files": [input_file], "data_format": data_format, "output": "exported-data"}
    ).model_dump(mode="json", by_alias=True, exclude_none=True, exclude_unset=True)

    seen: dict[str, int] = {"post": 0, "get": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/exported-form-data":
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
                    output_name,
                    mime_type,
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.export_form_data(
            input_file,
            data_format=data_format,
            output="exported-data",
        )

    assert seen == {"post": 1, "get": 1}
    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.output_file.name == output_name
    assert response.output_file.type == mime_type
    assert str(response.input_id) == str(input_file.id)
    assert response.warning is None


def test_export_form_data_request_customization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(1))
    output_id = str(PdfRestFileID.generate())
    captured_timeout: dict[str, float | dict[str, float] | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/exported-form-data":
            assert request.url.params["trace"] == "true"
            assert request.headers["X-Debug"] == "sync"
            captured_timeout["value"] = request.extensions.get("timeout")
            payload = json.loads(request.content.decode("utf-8"))
            assert payload["id"] == str(input_file.id)
            assert payload["data_format"] == "fdf"
            assert payload["output"] == "custom-data"
            assert payload["flag"] == "yes"
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
                    "custom-data.fdf",
                    "application/vnd.fdf",
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.export_form_data(
            input_file,
            data_format="fdf",
            output="custom-data",
            extra_query={"trace": "true"},
            extra_headers={"X-Debug": "sync"},
            extra_body={"flag": "yes"},
            timeout=0.37,
        )

    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.output_file.name == "custom-data.fdf"
    timeout_value = captured_timeout["value"]
    assert timeout_value is not None
    if isinstance(timeout_value, dict):
        assert all(
            component == pytest.approx(0.37) for component in timeout_value.values()
        )
    else:
        assert timeout_value == pytest.approx(0.37)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("data_format", "output_name", "mime_type"),
    [
        pytest.param("fdf", "async-data.fdf", "application/vnd.fdf", id="fdf"),
        pytest.param(
            "xfdf",
            "async-data.xfdf",
            "application/vnd.adobe.xfdf",
            id="xfdf",
        ),
        pytest.param("xml", "async-data.xml", "application/xml", id="xml"),
        pytest.param(
            "xdp",
            "async-data.xdp",
            "application/vnd.adobe.xdp+xml",
            id="xdp",
        ),
        pytest.param(
            "xfd",
            "async-data.xfd",
            "application/vnd.adobe.xfd+xml",
            id="xfd",
        ),
    ],
)
async def test_async_export_form_data_success(
    monkeypatch: pytest.MonkeyPatch,
    data_format: ExportDataFormat,
    output_name: str,
    mime_type: str,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(2))
    output_id = str(PdfRestFileID.generate())

    payload_dump = PdfExportFormDataPayload.model_validate(
        {"files": [input_file], "data_format": data_format}
    ).model_dump(mode="json", by_alias=True, exclude_none=True, exclude_unset=True)

    seen: dict[str, int] = {"post": 0, "get": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/exported-form-data":
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
                    output_name,
                    mime_type,
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        response = await client.export_form_data(input_file, data_format=data_format)

    assert seen == {"post": 1, "get": 1}
    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.output_file.name == output_name
    assert response.output_file.type == mime_type
    assert str(response.input_id) == str(input_file.id)


@pytest.mark.asyncio
async def test_async_export_form_data_request_customization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(2))
    output_id = str(PdfRestFileID.generate())
    captured_timeout: dict[str, float | dict[str, float] | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/exported-form-data":
            assert request.url.params["trace"] == "async"
            assert request.headers["X-Debug"] == "async"
            captured_timeout["value"] = request.extensions.get("timeout")
            payload = json.loads(request.content.decode("utf-8"))
            assert payload["id"] == str(input_file.id)
            assert payload["data_format"] == "xml"
            assert payload["note"] == "details"
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
                    "async-custom.xml",
                    "application/xml",
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        response = await client.export_form_data(
            input_file,
            data_format="xml",
            extra_query={"trace": "async"},
            extra_headers={"X-Debug": "async"},
            extra_body={"note": "details"},
            timeout=0.62,
        )

    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.output_file.name == "async-custom.xml"
    timeout_value = captured_timeout["value"]
    assert timeout_value is not None
    if isinstance(timeout_value, dict):
        assert all(
            component == pytest.approx(0.62) for component in timeout_value.values()
        )
    else:
        assert timeout_value == pytest.approx(0.62)


def test_export_form_data_validation(monkeypatch: pytest.MonkeyPatch) -> None:
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
        pytest.raises(ValidationError, match="Must be a PDF file"),
    ):
        client.export_form_data(png_file, data_format="xml")

    with (
        PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client,
        pytest.raises(ValidationError, match="Input should be 'fdf'"),
    ):
        client.export_form_data(pdf_file, data_format="yaml")  # type: ignore[arg-type]

    with (
        PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client,
        pytest.raises(
            ValidationError, match="List should have at most 1 item after validation"
        ),
    ):
        client.export_form_data(
            [pdf_file, make_pdf_file(PdfRestFileID.generate())], data_format="xml"
        )


@pytest.mark.asyncio
async def test_async_export_form_data_validation(
    monkeypatch: pytest.MonkeyPatch,
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

    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        with pytest.raises(ValidationError, match="Must be a PDF file"):
            await client.export_form_data(png_file, data_format="xml")

    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        with pytest.raises(ValidationError, match="Input should be 'fdf'"):
            await client.export_form_data(
                pdf_file,
                data_format="yaml",  # type: ignore[arg-type]
            )

    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        with pytest.raises(
            ValidationError, match="List should have at most 1 item after validation"
        ):
            await client.export_form_data(
                [pdf_file, make_pdf_file(PdfRestFileID.generate())],
                data_format="xml",
            )
