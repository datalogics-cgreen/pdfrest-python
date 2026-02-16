from __future__ import annotations

import json

import httpx
import pytest
from pydantic import ValidationError

from pdfrest import AsyncPdfRestClient, PdfRestClient
from pdfrest.models import PdfRestFileBasedResponse, PdfRestFileID
from pdfrest.models._internal import ConvertHtmlToPdfPayload

from .convert_to_pdf_test_helpers import make_source_file
from .graphics_test_helpers import ASYNC_API_KEY, VALID_API_KEY, build_file_info_payload


def test_convert_html_to_pdf_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_source_file(
        str(PdfRestFileID.generate(2)),
        "text/html",
        "example.html",
    )
    output_id = str(PdfRestFileID.generate())

    payload_dump = ConvertHtmlToPdfPayload.model_validate(
        {
            "files": [input_file],
            "output": "html-out",
            "page_size": "A4",
            "page_margin": "10mm",
            "page_orientation": "landscape",
            "web_layout": "tablet",
            "compression": "lossy",
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
        response = client.convert_html_to_pdf(
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


def test_convert_html_to_pdf_request_customization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_source_file(
        str(PdfRestFileID.generate(1)),
        "text/html",
        "example.html",
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
            assert payload["downsample"] == 300
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
        response = client.convert_html_to_pdf(
            input_file,
            output="custom",
            downsample=300,
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


def test_convert_html_to_pdf_validation_errors() -> None:
    with pytest.raises(ValidationError, match="Must be an HTML file"):
        ConvertHtmlToPdfPayload.model_validate(
            {
                "files": [
                    make_source_file(
                        str(PdfRestFileID.generate(2)),
                        "application/msword",
                        "example.doc",
                    )
                ]
            }
        )

    with pytest.raises(ValidationError, match="page_margin must be a number"):
        ConvertHtmlToPdfPayload.model_validate(
            {
                "files": [
                    make_source_file(
                        str(PdfRestFileID.generate()),
                        "text/html",
                        "example.html",
                    )
                ],
                "page_margin": "bad-margin",
            }
        )


@pytest.mark.asyncio
async def test_async_convert_html_to_pdf_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_source_file(
        str(PdfRestFileID.generate(2)),
        "text/html",
        "example.html",
    )
    output_id = str(PdfRestFileID.generate())
    payload_dump = ConvertHtmlToPdfPayload.model_validate(
        {
            "files": [input_file],
            "output": "async-converted",
            "compression": "lossy",
            "downsample": 300,
            "page_size": "letter",
            "page_margin": "1.0in",
            "page_orientation": "portrait",
            "web_layout": "desktop",
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
        response = await client.convert_html_to_pdf(
            input_file,
            output="async-converted",
            page_orientation="portrait",
        )

    assert seen == {"post": 1, "get": 1}
    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.output_file.name == "async-converted.pdf"
    assert response.output_file.type == "application/pdf"
    assert str(response.input_id) == str(input_file.id)
