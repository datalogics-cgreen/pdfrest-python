from __future__ import annotations

import json
import re

import httpx
import pytest
from pydantic import ValidationError

from pdfrest import AsyncPdfRestClient, PdfRestClient
from pdfrest.models import PdfRestFileBasedResponse, PdfRestFileID
from pdfrest.models._internal import PdfAddImagePayload

from .graphics_test_helpers import (
    ASYNC_API_KEY,
    VALID_API_KEY,
    build_file_info_payload,
    make_image_file,
    make_pdf_file,
)


def test_add_image_to_pdf_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    pdf_file = make_pdf_file(PdfRestFileID.generate(1))
    image_file = make_image_file(
        PdfRestFileID.generate(2), mime_type="image/jpeg", name="logo.jpg"
    )
    output_id = str(PdfRestFileID.generate())

    request_payload = PdfAddImagePayload.model_validate(
        {
            "files": [pdf_file],
            "image": [image_file],
            "x": 12,
            "y": 34,
            "page": 3,
            "output": "with-image",
        }
    ).model_dump(mode="json", by_alias=True, exclude_none=True, exclude_unset=True)

    seen: dict[str, int] = {"post": 0, "get": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/pdf-with-added-image":
            seen["post"] += 1
            assert request.headers["wsn"] == "pdfrest-python"
            payload = json.loads(request.content.decode("utf-8"))
            assert payload == request_payload
            return httpx.Response(
                200,
                json={
                    "inputId": [pdf_file.id, image_file.id],
                    "outputId": [output_id],
                },
            )
        if request.method == "GET" and request.url.path == f"/resource/{output_id}":
            seen["get"] += 1
            assert request.url.params["format"] == "info"
            return httpx.Response(
                200,
                json=build_file_info_payload(
                    output_id, "with-image.pdf", "application/pdf"
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.add_image_to_pdf(
            pdf_file,
            image=image_file,
            x=12,
            y=34,
            page=3,
            output="with-image",
        )

    assert seen == {"post": 1, "get": 1}
    assert isinstance(response, PdfRestFileBasedResponse)
    assert len(response.input_ids) == 2
    assert pdf_file.id in response.input_ids
    assert image_file.id in response.input_ids
    output_file = response.output_file
    assert output_file.name == "with-image.pdf"
    assert output_file.type == "application/pdf"
    assert output_file.size == 256
    assert str(output_file.url).endswith(output_id)
    assert response.warning is None


def test_add_image_to_pdf_request_customization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    pdf_file = make_pdf_file(PdfRestFileID.generate(1))
    image_file = make_image_file(PdfRestFileID.generate(2))
    output_id = "3fa85f64-5717-4562-b3fc-2c963f66afa6"
    captured_timeout: dict[str, float | dict[str, float] | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/pdf-with-added-image":
            assert request.url.params["trace"] == "true"
            assert request.headers["X-Debug"] == "1"
            payload = json.loads(request.content.decode("utf-8"))
            assert payload["x"] == 100
            assert payload["y"] == 200
            assert payload["page"] == 1
            assert payload["id"] == str(pdf_file.id)
            assert payload["image_id"] == str(image_file.id)
            captured_timeout["value"] = request.extensions.get("timeout")
            return httpx.Response(
                200,
                json={
                    "inputId": [pdf_file.id, image_file.id],
                    "outputId": [output_id],
                },
            )
        if request.method == "GET" and request.url.path == f"/resource/{output_id}":
            assert request.url.params["format"] == "info"
            assert request.url.params["trace"] == "true"
            assert request.headers["X-Debug"] == "1"
            return httpx.Response(
                200,
                json=build_file_info_payload(
                    output_id, "custom-with-image.pdf", "application/pdf"
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.add_image_to_pdf(
            pdf_file,
            image=image_file,
            x=100,
            y=200,
            page=1,
            extra_query={"trace": "true"},
            extra_headers={"X-Debug": "1"},
            extra_body={"page": 1},
            timeout=0.5,
        )

    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.output_files[0].name == "custom-with-image.pdf"
    timeout_value = captured_timeout["value"]
    assert timeout_value is not None
    if isinstance(timeout_value, dict):
        assert all(
            component == pytest.approx(0.5) for component in timeout_value.values()
        )
    else:
        assert timeout_value == pytest.approx(0.5)


def test_add_image_to_pdf_pdf_mime_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)

    def handler(_: httpx.Request) -> httpx.Response:
        pytest.fail("Request should not be sent when validation fails.")

    transport = httpx.MockTransport(handler)
    with (
        PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client,
        pytest.raises(ValidationError, match="Must be a PDF file"),
    ):
        client.add_image_to_pdf(
            make_image_file(PdfRestFileID.generate(1)),
            image=make_image_file(PdfRestFileID.generate(2)),
            x=1,
            y=2,
            page=1,
        )


def test_add_image_to_pdf_image_mime_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)

    def handler(_: httpx.Request) -> httpx.Response:
        pytest.fail("Request should not be sent when validation fails.")

    transport = httpx.MockTransport(handler)
    with (
        PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client,
        pytest.raises(
            ValidationError, match=re.escape("Image must be JPEG, PNG, TIFF, or GIF")
        ),
    ):
        client.add_image_to_pdf(
            make_pdf_file(PdfRestFileID.generate(1)),
            image=make_pdf_file(PdfRestFileID.generate(2)),
            x=1,
            y=2,
            page=1,
        )


def test_add_image_to_pdf_page_minimum(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)

    def handler(_: httpx.Request) -> httpx.Response:
        pytest.fail("Request should not be sent when validation fails.")

    transport = httpx.MockTransport(handler)
    with (
        PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client,
        pytest.raises(ValidationError, match="greater than or equal to 1"),
    ):
        client.add_image_to_pdf(
            make_pdf_file(PdfRestFileID.generate(1)),
            image=make_image_file(PdfRestFileID.generate(2)),
            x=0,
            y=0,
            page=0,
        )


@pytest.mark.asyncio
async def test_async_add_image_to_pdf_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    pdf_file = make_pdf_file(PdfRestFileID.generate(1))
    image_file = make_image_file(PdfRestFileID.generate(2), mime_type="image/gif")
    output_id = str(PdfRestFileID.generate())

    request_payload = PdfAddImagePayload.model_validate(
        {
            "files": [pdf_file],
            "image": [image_file],
            "x": 5,
            "y": 6,
            "page": 7,
        }
    ).model_dump(mode="json", by_alias=True, exclude_none=True, exclude_unset=True)

    seen: dict[str, int] = {"post": 0, "get": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/pdf-with-added-image":
            seen["post"] += 1
            payload = json.loads(request.content.decode("utf-8"))
            assert payload == request_payload
            return httpx.Response(
                200,
                json={
                    "inputId": [pdf_file.id, image_file.id],
                    "outputId": [output_id],
                },
            )
        if request.method == "GET" and request.url.path == f"/resource/{output_id}":
            seen["get"] += 1
            return httpx.Response(
                200,
                json=build_file_info_payload(
                    output_id, "async-with-image.pdf", "application/pdf"
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        response = await client.add_image_to_pdf(
            pdf_file,
            image=image_file,
            x=5,
            y=6,
            page=7,
        )

    assert seen == {"post": 1, "get": 1}
    assert response.output_files[0].name == "async-with-image.pdf"
    assert len(response.input_ids) == 2


@pytest.mark.asyncio
async def test_async_add_image_to_pdf_request_customization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    pdf_file = make_pdf_file(PdfRestFileID.generate(1))
    image_file = make_image_file(PdfRestFileID.generate(2))
    output_id = str(PdfRestFileID.generate())

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/pdf-with-added-image":
            assert request.url.params["trace"] == "true"
            assert request.headers["X-Test"] == "async"
            payload = json.loads(request.content.decode("utf-8"))
            assert payload["x"] == 15
            assert payload["y"] == 25
            return httpx.Response(
                200,
                json={
                    "inputId": [pdf_file.id, image_file.id],
                    "outputId": [output_id],
                },
            )
        if request.method == "GET" and request.url.path == f"/resource/{output_id}":
            assert request.url.params["trace"] == "true"
            assert request.headers["X-Test"] == "async"
            return httpx.Response(
                200,
                json=build_file_info_payload(
                    output_id, "async-custom-with-image.pdf", "application/pdf"
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        response = await client.add_image_to_pdf(
            pdf_file,
            image=image_file,
            x=15,
            y=25,
            page=1,
            extra_query={"trace": "true"},
            extra_headers={"X-Test": "async"},
            extra_body={"x": 15},
            timeout=1.0,
        )

    assert response.output_files[0].name == "async-custom-with-image.pdf"


@pytest.mark.asyncio
async def test_async_add_image_to_pdf_invalid_image_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)

    def handler(_: httpx.Request) -> httpx.Response:
        pytest.fail("Request should not be sent when validation fails.")

    transport = httpx.MockTransport(handler)
    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        with pytest.raises(
            ValidationError, match=re.escape("Image must be JPEG, PNG, TIFF, or GIF")
        ):
            await client.add_image_to_pdf(
                make_pdf_file(PdfRestFileID.generate(1)),
                image=make_pdf_file(PdfRestFileID.generate(2)),
                x=1,
                y=1,
                page=1,
            )
