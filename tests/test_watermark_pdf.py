from __future__ import annotations

import json
import re

import httpx
import pytest
from pydantic import ValidationError

from pdfrest import AsyncPdfRestClient, PdfRestClient
from pdfrest.models import PdfRestFile, PdfRestFileBasedResponse, PdfRestFileID
from pdfrest.models._internal import PdfImageWatermarkPayload, PdfTextWatermarkPayload

from .graphics_test_helpers import (
    ASYNC_API_KEY,
    VALID_API_KEY,
    build_file_info_payload,
    make_pdf_file,
)


def test_watermark_pdf_with_text(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(1))
    output_id = str(PdfRestFileID.generate())

    payload_dump = PdfTextWatermarkPayload.model_validate(
        {
            "files": [input_file],
            "watermark_text": "Confidential",
            "text_size": 72,
            "text_color_rgb": (255, 0, 0),
            "opacity": 0.5,
            "horizontal_alignment": "center",
            "vertical_alignment": "center",
            "x": 0,
            "y": 0,
            "rotation": 0,
            "pages": ["1", "3-5"],
            "behind_page": False,
            "output": "watermarked",
        }
    ).model_dump(mode="json", by_alias=True, exclude_none=True, exclude_unset=True)

    seen: dict[str, int] = {"post": 0, "get": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/watermarked-pdf":
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
                    "watermarked.pdf",
                    "application/pdf",
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.watermark_pdf_with_text(
            input_file,
            watermark_text="Confidential",
            text_color_rgb=(255, 0, 0),
            pages=["1", "3-5"],
            output="watermarked",
        )

    assert seen == {"post": 1, "get": 1}
    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.output_file.name == "watermarked.pdf"
    assert response.output_file.type == "application/pdf"
    assert str(response.input_id) == str(input_file.id)


def test_watermark_pdf_with_image(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(1))
    watermark_file = make_pdf_file(PdfRestFileID.generate(1), name="stamp.pdf")
    output_id = str(PdfRestFileID.generate())

    payload_dump = PdfImageWatermarkPayload.model_validate(
        {
            "files": [input_file],
            "watermark_file": [watermark_file],
            "watermark_file_scale": 0.8,
            "opacity": 0.5,
            "horizontal_alignment": "center",
            "vertical_alignment": "center",
            "x": 0,
            "behind_page": True,
            "rotation": 45,
            "y": 25,
        }
    ).model_dump(mode="json", by_alias=True, exclude_none=True, exclude_unset=True)

    seen: dict[str, int] = {"post": 0, "get": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/watermarked-pdf":
            seen["post"] += 1
            payload = json.loads(request.content.decode("utf-8"))
            assert payload == payload_dump
            return httpx.Response(
                200,
                json={
                    "inputId": [input_file.id, watermark_file.id],
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
                    "stamped.pdf",
                    "application/pdf",
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.watermark_pdf_with_image(
            input_file,
            watermark_file=watermark_file,
            watermark_file_scale=0.8,
            behind_page=True,
            rotation=45,
            y=25,
        )

    assert seen == {"post": 1, "get": 1}
    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.output_file.name == "stamped.pdf"
    assert response.output_file.type == "application/pdf"
    assert response.warning is None
    assert [str(value) for value in response.input_ids] == [
        str(input_file.id),
        str(watermark_file.id),
    ]


def test_watermark_pdf_with_text_request_customization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(1))
    output_id = str(PdfRestFileID.generate())
    captured_timeout: dict[str, float | dict[str, float] | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/watermarked-pdf":
            assert request.url.params["trace"] == "true"
            assert request.headers["X-Debug"] == "sync"
            captured_timeout["value"] = request.extensions.get("timeout")
            payload = json.loads(request.content.decode("utf-8"))
            assert payload["watermark_text"] == "Draft"
            assert payload["text_color_cmyk"] == "0,0,0,50"
            assert payload["opacity"] == 0.25
            assert payload["output"] == "custom"
            assert payload["debug"] == "yes"
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
        response = client.watermark_pdf_with_text(
            input_file,
            watermark_text="Draft",
            text_color_cmyk=(0, 0, 0, 50),
            opacity=0.25,
            output="custom",
            extra_query={"trace": "true"},
            extra_headers={"X-Debug": "sync"},
            extra_body={"debug": "yes"},
            timeout=0.31,
        )

    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.output_file.name == "custom.pdf"
    timeout_value = captured_timeout["value"]
    assert timeout_value is not None
    if isinstance(timeout_value, dict):
        assert all(
            component == pytest.approx(0.31) for component in timeout_value.values()
        )
    else:
        assert timeout_value == pytest.approx(0.31)


def test_watermark_pdf_with_text_validation_color_choice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(1))
    with (
        PdfRestClient(
            api_key=VALID_API_KEY,
            transport=httpx.MockTransport(
                lambda _: (_ for _ in ()).throw(RuntimeError("Should not be called"))
            ),
        ) as client,
        pytest.raises(
            ValidationError,
            match=re.escape("Specify only one of text_color_rgb or text_color_cmyk."),
        ),
    ):
        client.watermark_pdf_with_text(
            input_file,
            watermark_text="Confidential",
            text_color_rgb=(0, 0, 0),
            text_color_cmyk=(0, 0, 0, 0),
        )


def test_watermark_pdf_with_text_validation_rejects_non_pdf(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    bad_file = PdfRestFile.model_validate(
        {
            "id": str(PdfRestFileID.generate()),
            "name": "image.png",
            "type": "image/png",
            "url": "https://example.com/image.png",
            "size": 12,
            "modified": "2024-01-01T00:00:00Z",
        }
    )
    with (
        PdfRestClient(
            api_key=VALID_API_KEY,
            transport=httpx.MockTransport(
                lambda _: (_ for _ in ()).throw(RuntimeError("Should not be called"))
            ),
        ) as client,
        pytest.raises(ValidationError, match="Must be a PDF file"),
    ):
        client.watermark_pdf_with_text(bad_file, watermark_text="Hi")


def test_watermark_pdf_with_image_validation_rejects_non_pdf_watermark(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(1))
    bad_watermark = PdfRestFile.model_validate(
        {
            "id": str(PdfRestFileID.generate()),
            "name": "overlay.png",
            "type": "image/png",
            "url": "https://example.com/overlay.png",
            "size": 12,
            "modified": "2024-01-01T00:00:00Z",
        }
    )
    with (
        PdfRestClient(
            api_key=VALID_API_KEY,
            transport=httpx.MockTransport(
                lambda _: (_ for _ in ()).throw(RuntimeError("Should not be called"))
            ),
        ) as client,
        pytest.raises(ValidationError, match="Must be a PDF file"),
    ):
        client.watermark_pdf_with_image(input_file, watermark_file=bad_watermark)


def test_watermark_pdf_with_text_validation_rejects_short_text_size(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(1))
    with (
        PdfRestClient(
            api_key=VALID_API_KEY,
            transport=httpx.MockTransport(
                lambda _: (_ for _ in ()).throw(RuntimeError("Should not be called"))
            ),
        ) as client,
        pytest.raises(
            ValidationError, match="Input should be greater than or equal to 5"
        ),
    ):
        client.watermark_pdf_with_text(input_file, watermark_text="Hi", text_size=4)


@pytest.mark.asyncio
async def test_async_watermark_pdf_with_text(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(2))
    output_id = str(PdfRestFileID.generate())

    payload_dump = PdfTextWatermarkPayload.model_validate(
        {
            "files": [input_file],
            "watermark_text": "Async",
            "text_size": 72,
            "opacity": 0.6,
            "horizontal_alignment": "center",
            "vertical_alignment": "center",
            "x": 0,
            "y": 0,
            "rotation": 0,
            "behind_page": False,
        }
    ).model_dump(mode="json", by_alias=True, exclude_none=True, exclude_unset=True)

    seen: dict[str, int] = {"post": 0, "get": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/watermarked-pdf":
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
                    "async-watermarked.pdf",
                    "application/pdf",
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        response = await client.watermark_pdf_with_text(
            input_file,
            watermark_text="Async",
            opacity=0.6,
        )

    assert seen == {"post": 1, "get": 1}
    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.output_file.name == "async-watermarked.pdf"
    assert response.output_file.type == "application/pdf"
    assert str(response.input_id) == str(input_file.id)


@pytest.mark.asyncio
async def test_async_watermark_pdf_with_image(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(2))
    watermark_file = make_pdf_file(PdfRestFileID.generate(2), name="async-stamp.pdf")
    output_id = str(PdfRestFileID.generate())

    payload_dump = PdfImageWatermarkPayload.model_validate(
        {
            "files": [input_file],
            "watermark_file": [watermark_file],
            "watermark_file_scale": 0.5,
            "opacity": 0.2,
            "horizontal_alignment": "center",
            "vertical_alignment": "center",
            "x": 0,
            "y": 0,
            "rotation": 0,
            "pages": ["2-last"],
            "behind_page": False,
        }
    ).model_dump(mode="json", by_alias=True, exclude_none=True, exclude_unset=True)

    seen: dict[str, int] = {"post": 0, "get": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/watermarked-pdf":
            seen["post"] += 1
            payload = json.loads(request.content.decode("utf-8"))
            assert payload == payload_dump
            return httpx.Response(
                200,
                json={
                    "inputId": [input_file.id, watermark_file.id],
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
                    "async-stamped.pdf",
                    "application/pdf",
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        response = await client.watermark_pdf_with_image(
            input_file,
            watermark_file=watermark_file,
            opacity=0.2,
            pages=["2-last"],
        )

    assert seen == {"post": 1, "get": 1}
    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.output_file.name == "async-stamped.pdf"
    assert response.output_file.type == "application/pdf"
    assert [str(value) for value in response.input_ids] == [
        str(input_file.id),
        str(watermark_file.id),
    ]


@pytest.mark.asyncio
async def test_async_watermark_pdf_with_text_request_customization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(2))
    output_id = str(PdfRestFileID.generate())
    captured_timeout: dict[str, float | dict[str, float] | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/watermarked-pdf":
            assert request.url.params["trace"] == "async"
            assert request.headers["X-Debug"] == "async"
            captured_timeout["value"] = request.extensions.get("timeout")
            payload = json.loads(request.content.decode("utf-8"))
            assert payload["watermark_text"] == "AsyncDraft"
            assert payload["horizontal_alignment"] == "left"
            assert payload["vertical_alignment"] == "bottom"
            assert payload["x"] == -72
            assert payload["y"] == 144
            assert payload["rotation"] == 30
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
        response = await client.watermark_pdf_with_text(
            input_file,
            watermark_text="AsyncDraft",
            horizontal_alignment="left",
            vertical_alignment="bottom",
            x=-72,
            y=144,
            rotation=30,
            extra_query={"trace": "async"},
            extra_headers={"X-Debug": "async"},
            extra_body={"debug": "async"},
            timeout=0.42,
        )

    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.output_file.name == "async-custom.pdf"
    timeout_value = captured_timeout["value"]
    assert timeout_value is not None
    if isinstance(timeout_value, dict):
        assert all(
            component == pytest.approx(0.42) for component in timeout_value.values()
        )
    else:
        assert timeout_value == pytest.approx(0.42)
