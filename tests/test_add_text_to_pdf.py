from __future__ import annotations

import json
import re

import httpx
import pytest
from pydantic import ValidationError

from pdfrest import AsyncPdfRestClient, PdfRestClient
from pdfrest.models import PdfRestFileBasedResponse, PdfRestFileID
from pdfrest.models._internal import PdfAddTextPayload

from .graphics_test_helpers import (
    ASYNC_API_KEY,
    VALID_API_KEY,
    build_file_info_payload,
    make_pdf_file,
)


def make_text_object(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "font": "courier",
        "max_width": 200,
        "opacity": 0.75,
        "page": 1,
        "rotation": 0,
        "text": "Hello, PDF!",
        "text_color_rgb": (0, 0, 0),
        "text_size": 12,
        "x": 72,
        "y": 144,
    }
    base.update(overrides)
    return base


def test_add_text_to_pdf_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    pdf_file = make_pdf_file(PdfRestFileID.generate(1))
    output_id = str(PdfRestFileID.generate())

    request_payload = PdfAddTextPayload.model_validate(
        {
            "files": [pdf_file],
            "text_objects": [make_text_object()],
            "output": "with-text",
        }
    ).model_dump(mode="json", by_alias=True, exclude_none=True, exclude_unset=True)

    seen: dict[str, int] = {"post": 0, "get": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/pdf-with-added-text":
            seen["post"] += 1
            payload = json.loads(request.content.decode("utf-8"))
            assert payload == request_payload
            return httpx.Response(
                200,
                json={
                    "inputId": [pdf_file.id],
                    "outputId": [output_id],
                },
            )
        if request.method == "GET" and request.url.path == f"/resource/{output_id}":
            seen["get"] += 1
            return httpx.Response(
                200,
                json=build_file_info_payload(
                    output_id,
                    "with-text.pdf",
                    "application/pdf",
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.add_text_to_pdf(
            pdf_file,
            text_objects=[make_text_object()],
            output="with-text",
        )

    assert seen == {"post": 1, "get": 1}
    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.output_file.name == "with-text.pdf"
    assert response.output_file.type == "application/pdf"
    assert str(pdf_file.id) in [str(file_id) for file_id in response.input_ids]
    assert response.warning is None


def test_add_text_to_pdf_request_customization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    pdf_file = make_pdf_file(PdfRestFileID.generate(1))
    output_id = str(PdfRestFileID.generate())
    captured_timeout: dict[str, float | dict[str, float] | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/pdf-with-added-text":
            assert request.url.params["trace"] == "true"
            assert request.headers["X-Debug"] == "1"
            payload = json.loads(request.content.decode("utf-8"))
            assert payload["rotation"] == 15
            captured_timeout["value"] = request.extensions.get("timeout")
            return httpx.Response(
                200,
                json={
                    "inputId": [pdf_file.id],
                    "outputId": [output_id],
                },
            )
        if request.method == "GET" and request.url.path == f"/resource/{output_id}":
            assert request.url.params["trace"] == "true"
            assert request.headers["X-Debug"] == "1"
            return httpx.Response(
                200,
                json=build_file_info_payload(
                    output_id,
                    "custom-text.pdf",
                    "application/pdf",
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.add_text_to_pdf(
            pdf_file,
            text_objects=[make_text_object(rotation=15)],
            extra_query={"trace": "true"},
            extra_headers={"X-Debug": "1"},
            extra_body={"rotation": 15},
            timeout=0.25,
        )

    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.output_files[0].name == "custom-text.pdf"
    timeout_value = captured_timeout["value"]
    assert timeout_value is not None
    if isinstance(timeout_value, dict):
        assert all(
            component == pytest.approx(0.25) for component in timeout_value.values()
        )
    else:
        assert timeout_value == pytest.approx(0.25)


def test_add_text_to_pdf_requires_color(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)

    def handler(_: httpx.Request) -> httpx.Response:
        pytest.fail("Request should not be sent when validation fails.")

    transport = httpx.MockTransport(handler)
    text_object = make_text_object()
    text_object.pop("text_color_rgb")

    with (
        PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client,
        pytest.raises(
            ValidationError,
            match=re.escape(
                "Either text_color_rgb or text_color_cmyk must be provided."
            ),
        ),
    ):
        client.add_text_to_pdf(
            make_pdf_file(PdfRestFileID.generate(1)),
            text_objects=[text_object],
        )


def test_add_text_to_pdf_rgb_bounds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)

    def handler(_: httpx.Request) -> httpx.Response:
        pytest.fail("Request should not be sent when validation fails.")

    transport = httpx.MockTransport(handler)
    with (
        PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client,
        pytest.raises(
            ValidationError,
            match=re.escape("text_color_rgb values must be between 0 and 255."),
        ),
    ):
        client.add_text_to_pdf(
            make_pdf_file(PdfRestFileID.generate(1)),
            text_objects=[make_text_object(text_color_rgb=(0, 0, 256))],
        )


def test_add_text_to_pdf_text_size_bounds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)

    def handler(_: httpx.Request) -> httpx.Response:
        pytest.fail("Request should not be sent when validation fails.")

    transport = httpx.MockTransport(handler)
    with (
        PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client,
        pytest.raises(ValidationError, match="greater than or equal to 5"),
    ):
        client.add_text_to_pdf(
            make_pdf_file(PdfRestFileID.generate(1)),
            text_objects=[make_text_object(text_size=4)],
        )


@pytest.mark.asyncio
async def test_async_add_text_to_pdf_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    pdf_file = make_pdf_file(PdfRestFileID.generate(1))
    output_id = str(PdfRestFileID.generate())

    request_payload = PdfAddTextPayload.model_validate(
        {
            "files": [pdf_file],
            "text_objects": [make_text_object(page="all")],
        }
    ).model_dump(mode="json", by_alias=True, exclude_none=True, exclude_unset=True)

    seen: dict[str, int] = {"post": 0, "get": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/pdf-with-added-text":
            seen["post"] += 1
            payload = json.loads(request.content.decode("utf-8"))
            assert payload == request_payload
            return httpx.Response(
                200,
                json={
                    "inputId": [pdf_file.id],
                    "outputId": [output_id],
                },
            )
        if request.method == "GET" and request.url.path == f"/resource/{output_id}":
            seen["get"] += 1
            return httpx.Response(
                200,
                json=build_file_info_payload(
                    output_id,
                    "async-with-text.pdf",
                    "application/pdf",
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        response = await client.add_text_to_pdf(
            pdf_file,
            text_objects=[make_text_object(page="all")],
        )

    assert seen == {"post": 1, "get": 1}
    assert response.output_files[0].name == "async-with-text.pdf"


@pytest.mark.asyncio
async def test_async_add_text_to_pdf_request_customization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    pdf_file = make_pdf_file(PdfRestFileID.generate(1))
    output_id = str(PdfRestFileID.generate())

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/pdf-with-added-text":
            assert request.url.params["trace"] == "true"
            assert request.headers["X-Test"] == "async"
            payload = json.loads(request.content.decode("utf-8"))
            assert payload["text_size"] == 18
            return httpx.Response(
                200,
                json={
                    "inputId": [pdf_file.id],
                    "outputId": [output_id],
                },
            )
        if request.method == "GET" and request.url.path == f"/resource/{output_id}":
            assert request.url.params["trace"] == "true"
            assert request.headers["X-Test"] == "async"
            return httpx.Response(
                200,
                json=build_file_info_payload(
                    output_id,
                    "async-custom-text.pdf",
                    "application/pdf",
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        response = await client.add_text_to_pdf(
            pdf_file,
            text_objects=[make_text_object(text_size=18)],
            extra_query={"trace": "true"},
            extra_headers={"X-Test": "async"},
            extra_body={"text_size": 18},
            timeout=1.0,
        )

    assert response.output_files[0].name == "async-custom-text.pdf"


@pytest.mark.asyncio
async def test_async_add_text_to_pdf_invalid_cmyk_range(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)

    def handler(_: httpx.Request) -> httpx.Response:
        pytest.fail("Request should not be sent when validation fails.")

    transport = httpx.MockTransport(handler)
    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        with pytest.raises(
            ValidationError,
            match=re.escape("text_color_cmyk values must be between 0 and 100."),
        ):
            await client.add_text_to_pdf(
                make_pdf_file(PdfRestFileID.generate(1)),
                text_objects=[
                    make_text_object(
                        text_color_rgb=None, text_color_cmyk=(0, 0, 0, 101)
                    )
                ],
            )
