from __future__ import annotations

import json

import httpx
import pytest
from pydantic import ValidationError

from pdfrest import AsyncPdfRestClient, PdfRestClient
from pdfrest.models import PdfRestFileBasedResponse, PdfRestFileID
from pdfrest.models._internal import ConvertUrlToPdfPayload

from .graphics_test_helpers import ASYNC_API_KEY, VALID_API_KEY, build_file_info_payload


def test_convert_url_to_pdf_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    url = "https://example.com/page"
    output_id = str(PdfRestFileID.generate())
    payload_dump = ConvertUrlToPdfPayload.model_validate(
        {
            "url": url,
            "output": "url-out",
            "compression": "lossy",
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
        response = client.convert_url_to_pdf(
            url,
            output="url-out",
            page_size="letter",
            page_margin="2.5in",
            page_orientation="portrait",
            web_layout="desktop",
            downsample=300,
        )

    assert response.output_file.name == "url-out.pdf"
    assert response.output_file.type == "application/pdf"


def test_convert_url_to_pdf_validation_errors() -> None:
    with pytest.raises(ValidationError, match="Input should be a valid URL"):
        ConvertUrlToPdfPayload.model_validate({"url": "not-a-url"})

    with pytest.raises(ValidationError, match="at least 1 item"):
        ConvertUrlToPdfPayload.model_validate({"url": []})

    with pytest.raises(ValidationError, match="at most 1 item"):
        ConvertUrlToPdfPayload.model_validate(
            {"url": ["https://example.com/one", "https://example.com/two"]}
        )

    with pytest.raises(ValidationError, match="String should match pattern"):
        ConvertUrlToPdfPayload.model_validate(
            {"url": "https://example.com", "page_margin": "mm"}
        )


@pytest.mark.parametrize(
    "page_margin",
    [
        pytest.param("8mm", id="whole-millimeters"),
        pytest.param("2.5in", id="decimal-inches"),
        pytest.param("10.25mm", id="long-decimal-millimeters"),
        pytest.param("0in", id="zero-inches"),
    ],
)
def test_convert_url_to_pdf_page_margin_accepts_documented_values(
    page_margin: str,
) -> None:
    payload = ConvertUrlToPdfPayload.model_validate(
        {"url": "https://example.com/page", "page_margin": page_margin}
    )

    assert payload.page_margin == page_margin


@pytest.mark.parametrize(
    "page_margin",
    [
        pytest.param("8", id="missing-unit"),
        pytest.param("mm", id="missing-number"),
        pytest.param("2.5 in", id="embedded-space"),
        pytest.param("8MM", id="uppercase-unit"),
        pytest.param(" 8mm", id="leading-space"),
        pytest.param("8mm ", id="trailing-space"),
    ],
)
def test_convert_url_to_pdf_page_margin_rejects_invalid_values(
    page_margin: str,
) -> None:
    with pytest.raises(ValidationError, match="String should match pattern"):
        ConvertUrlToPdfPayload.model_validate(
            {"url": "https://example.com/page", "page_margin": page_margin}
        )


def test_convert_url_to_pdf_request_customization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    url = "https://example.com/page"
    output_id = str(PdfRestFileID.generate())
    captured_timeout: dict[str, float | dict[str, float] | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/pdf":
            assert request.url.params["trace"] == "sync"
            assert request.headers["X-Debug"] == "sync"
            captured_timeout["value"] = request.extensions.get("timeout")
            payload = json.loads(request.content.decode("utf-8"))
            assert payload["url"] == url
            assert payload["output"] == "sync-url"
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
            assert request.url.params["trace"] == "sync"
            assert request.headers["X-Debug"] == "sync"
            return httpx.Response(
                200,
                json=build_file_info_payload(
                    output_id, "sync-url.pdf", "application/pdf"
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.convert_url_to_pdf(
            url,
            output="sync-url",
            page_orientation="portrait",
            extra_query={"trace": "sync"},
            extra_headers={"X-Debug": "sync"},
            extra_body={"debug": "yes"},
            timeout=0.5,
        )

    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.output_file.name == "sync-url.pdf"
    timeout_value = captured_timeout["value"]
    assert timeout_value is not None
    if isinstance(timeout_value, dict):
        assert all(
            component == pytest.approx(0.5) for component in timeout_value.values()
        )
    else:
        assert timeout_value == pytest.approx(0.5)


@pytest.mark.asyncio
async def test_async_convert_url_to_pdf_request_customization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    url = "https://example.com/page"
    output_id = str(PdfRestFileID.generate())
    captured_timeout: dict[str, float | dict[str, float] | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/pdf":
            assert request.url.params["trace"] == "async"
            assert request.headers["X-Debug"] == "async"
            captured_timeout["value"] = request.extensions.get("timeout")
            payload = json.loads(request.content.decode("utf-8"))
            assert payload["url"] == url
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
        response = await client.convert_url_to_pdf(
            url,
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
