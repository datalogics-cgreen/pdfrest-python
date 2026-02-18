from __future__ import annotations

import json

import httpx
import pytest
from pydantic import ValidationError

from pdfrest import AsyncPdfRestClient, PdfRestClient
from pdfrest.models import PdfRestFile, PdfRestFileBasedResponse, PdfRestFileID
from pdfrest.models._internal import PdfImportFormDataPayload

from .graphics_test_helpers import (
    ASYNC_API_KEY,
    VALID_API_KEY,
    build_file_info_payload,
    make_pdf_file,
)

ACCEPTED_IMPORT_DATA_FILE_MIME_TYPES = (
    pytest.param("application/xml", id="application-xml"),
    pytest.param("text/xml", id="text-xml"),
    pytest.param("application/vnd.fdf", id="application-vnd-fdf"),
    pytest.param(
        "application/vnd.adobe.xfdf",
        id="application-vnd-adobe-xfdf",
    ),
    pytest.param(
        "application/vnd.adobe.xdp+xml",
        id="application-vnd-adobe-xdp+xml",
    ),
    pytest.param(
        "application/vnd.adobe.xfd+xml",
        id="application-vnd-adobe-xfd+xml",
    ),
)


def _make_data_file(
    file_id: PdfRestFileID, *, mime_type: str = "application/xml"
) -> PdfRestFile:
    file_name = "form-data.xml"
    if mime_type == "application/vnd.fdf":
        file_name = "form-data.fdf"
    elif mime_type == "application/vnd.adobe.xfdf":
        file_name = "form-data.xfdf"
    elif mime_type == "application/vnd.adobe.xdp+xml":
        file_name = "form-data.xdp"
    elif mime_type == "application/vnd.adobe.xfd+xml":
        file_name = "form-data.xfd"

    return PdfRestFile.model_validate(
        build_file_info_payload(file_id, file_name, mime_type)
    )


@pytest.mark.parametrize("data_file_mime", ACCEPTED_IMPORT_DATA_FILE_MIME_TYPES)
def test_import_form_data_success(
    monkeypatch: pytest.MonkeyPatch,
    data_file_mime: str,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(1))
    data_file = _make_data_file(PdfRestFileID.generate(2), mime_type=data_file_mime)
    output_id = str(PdfRestFileID.generate())

    payload_dump = PdfImportFormDataPayload.model_validate(
        {"files": [input_file], "data_file": [data_file], "output": "filled-form"}
    ).model_dump(mode="json", by_alias=True, exclude_none=True, exclude_unset=True)

    seen: dict[str, int] = {"post": 0, "get": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if (
            request.method == "POST"
            and request.url.path == "/pdf-with-imported-form-data"
        ):
            seen["post"] += 1
            payload = json.loads(request.content.decode("utf-8"))
            assert payload == payload_dump
            return httpx.Response(
                200,
                json={
                    "inputId": [input_file.id, data_file.id],
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
                    "filled-form.pdf",
                    "application/pdf",
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.import_form_data(
            input_file,
            data_file,
            output="filled-form",
        )

    assert seen == {"post": 1, "get": 1}
    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.output_file.name == "filled-form.pdf"
    assert response.output_file.type == "application/pdf"
    assert str(input_file.id) in {str(file_id) for file_id in response.input_ids}
    assert str(data_file.id) in {str(file_id) for file_id in response.input_ids}
    assert response.warning is None


def test_import_form_data_request_customization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(1))
    data_file = _make_data_file(PdfRestFileID.generate(2))
    output_id = str(PdfRestFileID.generate())
    captured_timeout: dict[str, float | dict[str, float] | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if (
            request.method == "POST"
            and request.url.path == "/pdf-with-imported-form-data"
        ):
            assert request.url.params["trace"] == "true"
            assert request.headers["X-Debug"] == "sync"
            captured_timeout["value"] = request.extensions.get("timeout")
            payload = json.loads(request.content.decode("utf-8"))
            assert payload["id"] == str(input_file.id)
            assert payload["data_file_id"] == str(data_file.id)
            assert payload["output"] == "custom-output"
            assert payload["debug"] == "flag"
            return httpx.Response(
                200,
                json={
                    "inputId": [input_file.id, data_file.id],
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
                    "custom.pdf",
                    "application/pdf",
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.import_form_data(
            input_file,
            data_file,
            output="custom-output",
            extra_query={"trace": "true"},
            extra_headers={"X-Debug": "sync"},
            extra_body={"debug": "flag"},
            timeout=0.41,
        )

    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.output_file.name == "custom.pdf"
    timeout_value = captured_timeout["value"]
    assert timeout_value is not None
    if isinstance(timeout_value, dict):
        assert all(
            component == pytest.approx(0.41) for component in timeout_value.values()
        )
    else:
        assert timeout_value == pytest.approx(0.41)


@pytest.mark.asyncio
@pytest.mark.parametrize("data_file_mime", ACCEPTED_IMPORT_DATA_FILE_MIME_TYPES)
async def test_async_import_form_data_success(
    monkeypatch: pytest.MonkeyPatch,
    data_file_mime: str,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(2))
    data_file = _make_data_file(PdfRestFileID.generate(1), mime_type=data_file_mime)
    output_id = str(PdfRestFileID.generate())

    payload_dump = PdfImportFormDataPayload.model_validate(
        {"files": [input_file], "data_file": [data_file]}
    ).model_dump(mode="json", by_alias=True, exclude_none=True, exclude_unset=True)

    seen: dict[str, int] = {"post": 0, "get": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if (
            request.method == "POST"
            and request.url.path == "/pdf-with-imported-form-data"
        ):
            seen["post"] += 1
            payload = json.loads(request.content.decode("utf-8"))
            assert payload == payload_dump
            return httpx.Response(
                200,
                json={
                    "inputId": [input_file.id, data_file.id],
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
                    "async.pdf",
                    "application/pdf",
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        response = await client.import_form_data(input_file, data_file)

    assert seen == {"post": 1, "get": 1}
    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.output_file.name == "async.pdf"
    assert response.output_file.type == "application/pdf"
    assert str(input_file.id) in {str(file_id) for file_id in response.input_ids}
    assert str(data_file.id) in {str(file_id) for file_id in response.input_ids}


@pytest.mark.asyncio
async def test_async_import_form_data_request_customization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(2))
    data_file = _make_data_file(PdfRestFileID.generate(1))
    output_id = str(PdfRestFileID.generate())
    captured_timeout: dict[str, float | dict[str, float] | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if (
            request.method == "POST"
            and request.url.path == "/pdf-with-imported-form-data"
        ):
            assert request.url.params["trace"] == "async"
            assert request.headers["X-Debug"] == "async"
            captured_timeout["value"] = request.extensions.get("timeout")
            payload = json.loads(request.content.decode("utf-8"))
            assert payload["id"] == str(input_file.id)
            assert payload["data_file_id"] == str(data_file.id)
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
                    "async-custom.pdf",
                    "application/pdf",
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        response = await client.import_form_data(
            input_file,
            data_file,
            extra_query={"trace": "async"},
            extra_headers={"X-Debug": "async"},
            extra_body={"note": "details"},
            timeout=0.73,
        )

    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.output_file.name == "async-custom.pdf"
    timeout_value = captured_timeout["value"]
    assert timeout_value is not None
    if isinstance(timeout_value, dict):
        assert all(
            component == pytest.approx(0.73) for component in timeout_value.values()
        )
    else:
        assert timeout_value == pytest.approx(0.73)


def test_import_form_data_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    pdf_file = make_pdf_file(PdfRestFileID.generate(1))
    data_file = _make_data_file(PdfRestFileID.generate(2))
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
        client.import_form_data(png_file, data_file)

    with (
        PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client,
        pytest.raises(
            ValidationError,
            match="Data file must be an XFDF, XDP, XFD, FDF, or XML file",
        ),
    ):
        client.import_form_data(pdf_file, png_file)

    with (
        PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client,
        pytest.raises(
            ValidationError, match="List should have at most 1 item after validation"
        ),
    ):
        client.import_form_data(
            [pdf_file, make_pdf_file(PdfRestFileID.generate())],
            data_file,
        )

    with (
        PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client,
        pytest.raises(
            ValidationError, match="List should have at most 1 item after validation"
        ),
    ):
        client.import_form_data(
            pdf_file,
            [data_file, _make_data_file(PdfRestFileID.generate())],
        )


@pytest.mark.asyncio
async def test_async_import_form_data_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    pdf_file = make_pdf_file(PdfRestFileID.generate(1))
    data_file = _make_data_file(PdfRestFileID.generate(2))
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
            await client.import_form_data(png_file, data_file)

    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        with pytest.raises(
            ValidationError,
            match="Data file must be an XFDF, XDP, XFD, FDF, or XML file",
        ):
            await client.import_form_data(pdf_file, png_file)

    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        with pytest.raises(
            ValidationError, match="List should have at most 1 item after validation"
        ):
            await client.import_form_data(
                [pdf_file, make_pdf_file(PdfRestFileID.generate())],
                data_file,
            )

    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        with pytest.raises(
            ValidationError, match="List should have at most 1 item after validation"
        ):
            await client.import_form_data(
                pdf_file,
                [data_file, _make_data_file(PdfRestFileID.generate())],
            )
