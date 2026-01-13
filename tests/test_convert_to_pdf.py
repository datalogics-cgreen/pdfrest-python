from __future__ import annotations

import json

import httpx
import pytest
from pydantic import ValidationError

from pdfrest import AsyncPdfRestClient, PdfRestClient
from pdfrest.models import PdfRestFile, PdfRestFileBasedResponse, PdfRestFileID
from pdfrest.models._internal import ConvertToPdfPayload, ConvertUrlsToPdfPayload

from .graphics_test_helpers import (
    ASYNC_API_KEY,
    VALID_API_KEY,
    build_file_info_payload,
)


def make_source_file(file_id: str, mime_type: str, name: str) -> PdfRestFile:
    return PdfRestFile.model_validate(
        {
            "id": file_id,
            "name": name,
            "url": f"https://api.pdfrest.com/resource/{file_id}",
            "type": mime_type,
            "size": 512,
            "modified": "2024-01-01T00:00:00Z",
            "scheduledDeletionTimeUtc": None,
        }
    )


def test_convert_to_pdf_word_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_source_file(
        PdfRestFileID.generate(1),
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "example.docx",
    )
    output_id = str(PdfRestFileID.generate())
    payload_dump = ConvertToPdfPayload.model_validate(
        {
            "files": [input_file],
            "output": "converted",
            "compression": "lossless",
            "downsample": 150,
            "tagged_pdf": True,
        }
    ).model_dump(mode="json", by_alias=True, exclude_none=True, exclude_unset=True)

    seen: dict[str, int] = {"post": 0, "get": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/pdf":
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
                    output_id, "converted.pdf", "application/pdf"
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.convert_to_pdf(
            input_file,
            output="converted",
            compression="lossless",
            downsample=150,
            tagged_pdf=True,
        )

    assert seen == {"post": 1, "get": 1}
    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.output_file.name == "converted.pdf"
    assert response.output_file.type == "application/pdf"
    assert response.warning is None
    assert str(response.input_id) == str(input_file.id)


def test_convert_to_pdf_html_options_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_source_file(
        PdfRestFileID.generate(2),
        "text/html",
        "example.html",
    )
    output_id = str(PdfRestFileID.generate())

    payload_dump = ConvertToPdfPayload.model_validate(
        {
            "files": [input_file],
            "output": "html-out",
            "page_size": "A4",
            "page_margin": "10mm",
            "page_orientation": "landscape",
            "web_layout": "tablet",
            "compression": "lossy",
        }
    ).model_dump(mode="json", by_alias=True, exclude_none=True, exclude_unset=True)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/pdf":
            payload = json.loads(request.content.decode("utf-8"))
            assert payload == payload_dump
            return httpx.Response(
                200,
                json={
                    "inputId": [input_file.id],
                    "outputId": [output_id],
                    "warning": "html warning",
                },
            )
        if request.method == "GET" and request.url.path == f"/resource/{output_id}":
            return httpx.Response(
                200,
                json=build_file_info_payload(
                    output_id, "html-out.pdf", "application/pdf"
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.convert_to_pdf(
            input_file,
            output="html-out",
            page_size="A4",
            page_margin="10mm",
            page_orientation="landscape",
            web_layout="tablet",
            compression="lossy",
        )

    assert response.output_file.name == "html-out.pdf"
    assert response.output_file.type == "application/pdf"
    assert response.warning == "html warning"


def test_convert_urls_to_pdf_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    urls = ["https://example.com/page"]
    output_id = str(PdfRestFileID.generate())
    payload_dump = ConvertUrlsToPdfPayload.model_validate(
        {
            "url": urls,
            "output": "url-out",
            "page_size": "letter",
            "page_margin": "2.5in",
            "page_orientation": "portrait",
            "web_layout": "desktop",
            "downsample": 300,
        }
    ).model_dump(mode="json", by_alias=True, exclude_none=True, exclude_unset=True)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/pdf":
            payload = json.loads(request.content.decode("utf-8"))
            assert payload == payload_dump
            return httpx.Response(
                200,
                json={
                    "inputId": [PdfRestFileID.generate()],
                    "outputId": [output_id],
                },
            )
        if request.method == "GET" and request.url.path == f"/resource/{output_id}":
            return httpx.Response(
                200,
                json=build_file_info_payload(
                    output_id, "url-out.pdf", "application/pdf"
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.convert_urls_to_pdf(
            urls,
            output="url-out",
            page_size="letter",
            page_margin="2.5in",
            page_orientation="portrait",
            web_layout="desktop",
            downsample=300,
        )

    assert response.output_file.name == "url-out.pdf"
    assert response.output_file.type == "application/pdf"


def test_convert_to_pdf_request_customization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_source_file(
        PdfRestFileID.generate(1),
        "application/postscript",
        "example.ps",
    )
    output_id = str(PdfRestFileID.generate())
    captured_timeout: dict[str, float | dict[str, float] | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/pdf":
            assert request.url.params["trace"] == "true"
            assert request.headers["X-Debug"] == "sync"
            captured_timeout["value"] = request.extensions.get("timeout")
            payload = json.loads(request.content.decode("utf-8"))
            assert payload["debug"] is True
            assert payload["compression"] == "lossy"
            assert payload["downsample"] == 600
            assert payload["id"] == str(input_file.id)
            assert payload["output"] == "custom"
            return httpx.Response(
                200,
                json={
                    "inputId": [input_file.id],
                    "outputId": [output_id],
                },
            )
        if request.method == "GET" and request.url.path == f"/resource/{output_id}":
            assert request.url.params["trace"] == "true"
            assert request.headers["X-Debug"] == "sync"
            return httpx.Response(
                200,
                json=build_file_info_payload(
                    output_id, "custom.pdf", "application/pdf"
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.convert_to_pdf(
            input_file,
            output="custom",
            compression="lossy",
            downsample=600,
            extra_query={"trace": "true"},
            extra_headers={"X-Debug": "sync"},
            extra_body={"debug": True},
            timeout=0.5,
        )

    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.output_file.name == "custom.pdf"
    timeout_value = captured_timeout["value"]
    assert timeout_value is not None
    if isinstance(timeout_value, dict):
        assert all(
            component == pytest.approx(0.5) for component in timeout_value.values()
        )
    else:
        assert timeout_value == pytest.approx(0.5)


def test_convert_to_pdf_validation_errors() -> None:
    word_file = make_source_file(
        PdfRestFileID.generate(1),
        "application/msword",
        "example.doc",
    )
    image_file = make_source_file(
        PdfRestFileID.generate(2),
        "image/jpeg",
        "photo.jpg",
    )

    with pytest.raises(ValidationError, match="Must be a supported file type"):
        ConvertToPdfPayload.model_validate(
            {
                "files": [
                    make_source_file(
                        PdfRestFileID.generate(1),
                        "application/pdf",
                        "example.pdf",
                    )
                ]
            }
        )

    with pytest.raises(
        ValidationError, match="locale is only supported for Excel inputs"
    ):
        ConvertToPdfPayload.model_validate({"files": [word_file], "locale": "Germany"})

    with pytest.raises(
        ValidationError, match="page_size is only supported for HTML inputs"
    ):
        ConvertToPdfPayload.model_validate({"files": [word_file], "page_size": "A3"})

    with pytest.raises(
        ValidationError,
        match="compression and downsample are only supported",
    ):
        ConvertToPdfPayload.model_validate(
            {"files": [image_file], "compression": "lossless"}
        )

    with pytest.raises(ValidationError, match="page_margin must be a number"):
        ConvertToPdfPayload.model_validate(
            {"files": [word_file], "page_margin": "bad-margin"}
        )

    with pytest.raises(
        ValidationError,
        match="List should have at most 1 item after validation",
    ):
        ConvertToPdfPayload.model_validate({"files": [word_file, image_file]})


def test_convert_urls_to_pdf_validation_errors() -> None:
    with pytest.raises(ValidationError, match="Input should be a valid URL"):
        ConvertUrlsToPdfPayload.model_validate({"url": "not-a-url"})

    with pytest.raises(ValidationError, match="page_margin must be a number"):
        ConvertUrlsToPdfPayload.model_validate(
            {"url": ["https://example.com"], "page_margin": "mm"}
        )


@pytest.mark.asyncio
async def test_async_convert_to_pdf_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_source_file(
        PdfRestFileID.generate(2),
        "application/vnd.ms-excel",
        "sheet.xls",
    )
    output_id = str(PdfRestFileID.generate())
    payload_dump = ConvertToPdfPayload.model_validate(
        {
            "files": [input_file],
            "output": "async-converted",
            "locale": "US",
        }
    ).model_dump(mode="json", by_alias=True, exclude_none=True, exclude_unset=True)

    seen: dict[str, int] = {"post": 0, "get": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/pdf":
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
            return httpx.Response(
                200,
                json=build_file_info_payload(
                    output_id, "async-converted.pdf", "application/pdf"
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        response = await client.convert_to_pdf(
            input_file, output="async-converted", locale="US"
        )

    assert seen == {"post": 1, "get": 1}
    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.output_file.name == "async-converted.pdf"
    assert response.output_file.type == "application/pdf"
    assert str(response.input_id) == str(input_file.id)


@pytest.mark.asyncio
async def test_async_convert_urls_to_pdf_request_customization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    urls = ["https://example.com/page", "https://example.com/other"]
    output_id = str(PdfRestFileID.generate())
    captured_timeout: dict[str, float | dict[str, float] | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/pdf":
            assert request.url.params["trace"] == "async"
            assert request.headers["X-Debug"] == "async"
            captured_timeout["value"] = request.extensions.get("timeout")
            payload = json.loads(request.content.decode("utf-8"))
            assert payload["url"] == urls
            assert payload["output"] == "async-url"
            assert payload["page_orientation"] == "portrait"
            assert payload["debug"] == "yes"
            return httpx.Response(
                200,
                json={
                    "inputId": [PdfRestFileID.generate()],
                    "outputId": [output_id],
                },
            )
        if request.method == "GET" and request.url.path == f"/resource/{output_id}":
            assert request.url.params["trace"] == "async"
            assert request.headers["X-Debug"] == "async"
            return httpx.Response(
                200,
                json=build_file_info_payload(
                    output_id, "async-url.pdf", "application/pdf"
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        response = await client.convert_urls_to_pdf(
            urls,
            output="async-url",
            page_orientation="portrait",
            extra_query={"trace": "async"},
            extra_headers={"X-Debug": "async"},
            extra_body={"debug": "yes"},
            timeout=0.6,
        )

    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.output_file.name == "async-url.pdf"
    timeout_value = captured_timeout["value"]
    assert timeout_value is not None
    if isinstance(timeout_value, dict):
        assert all(
            component == pytest.approx(0.6) for component in timeout_value.values()
        )
    else:
        assert timeout_value == pytest.approx(0.6)
