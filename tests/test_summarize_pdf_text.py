from __future__ import annotations

import json

import httpx
import pytest
from pydantic import ValidationError

from pdfrest import AsyncPdfRestClient, PdfRestClient
from pdfrest.models import (
    PdfRestFile,
    PdfRestFileBasedResponse,
    PdfRestFileID,
    SummarizePdfTextResponse,
)
from pdfrest.models._internal import SummarizePdfTextPayload

from .graphics_test_helpers import (
    ASYNC_API_KEY,
    VALID_API_KEY,
    build_file_info_payload,
    make_pdf_file,
)


def _make_text_file(file_id: str) -> PdfRestFile:
    return PdfRestFile.model_validate(
        {
            "id": file_id,
            "name": "notes.txt",
            "url": f"https://api.pdfrest.com/resource/{file_id}",
            "type": "text/plain",
            "size": 64,
            "modified": "2024-01-01T00:00:00Z",
            "scheduledDeletionTimeUtc": None,
        }
    )


def test_summarize_payload_rejects_invalid_mime() -> None:
    file_id = str(PdfRestFileID.generate())
    image_file = PdfRestFile.model_validate(
        {
            "id": file_id,
            "name": "image.png",
            "url": f"https://api.pdfrest.com/resource/{file_id}",
            "type": "image/png",
            "size": 10,
            "modified": "2024-01-01T00:00:00Z",
            "scheduledDeletionTimeUtc": None,
        }
    )

    with pytest.raises(
        ValidationError, match="Must be a PDF, Markdown, or plain text file"
    ):
        SummarizePdfTextPayload.model_validate({"files": [image_file]})


def test_summarize_payload_invalid_page_range() -> None:
    file_repr = make_pdf_file(PdfRestFileID.generate(1))

    with pytest.raises(
        ValidationError, match="The start page must be less than or equal to the end"
    ):
        SummarizePdfTextPayload.model_validate({"files": [file_repr], "pages": ["5-2"]})


def test_summarize_pdf_text_json_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = _make_text_file(str(PdfRestFileID.generate(1)))
    payload_dump = SummarizePdfTextPayload.model_validate(
        {
            "files": [input_file],
            "target_word_count": 120,
            "summary_format": "bullet_points",
            "pages": ["1-3"],
            "output_format": "plaintext",
            "output_type": "json",
            "output": "summary",
        }
    ).model_dump(mode="json", by_alias=True, exclude_none=True, exclude_unset=True)

    seen: dict[str, int] = {"post": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/summarized-pdf-text":
            seen["post"] += 1
            payload = json.loads(request.content.decode("utf-8"))
            assert payload == payload_dump
            return httpx.Response(
                200,
                json={
                    "summary": "Key points...",
                    "inputId": str(input_file.id),
                },
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.summarize_pdf_text(
            input_file,
            target_word_count=120,
            summary_format="bullet_points",
            pages=["1-3"],
            output_format="plaintext",
            output="summary",
        )

    assert seen == {"post": 1}
    assert isinstance(response, SummarizePdfTextResponse)
    assert response.summary == "Key points..."
    assert response.input_id == input_file.id


def test_summarize_pdf_text_to_file_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = _make_text_file(str(PdfRestFileID.generate(1)))
    payload_dump = SummarizePdfTextPayload.model_validate(
        {
            "files": [input_file],
            "target_word_count": 200,
            "summary_format": "bullet_points",
            "pages": ["2-last"],
            "output_format": "plaintext",
            "output_type": "file",
            "output": "summary",
        }
    ).model_dump(mode="json", by_alias=True, exclude_none=True, exclude_unset=True)
    output_id = str(PdfRestFileID.generate())

    seen: dict[str, int] = {"post": 0, "get": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/summarized-pdf-text":
            seen["post"] += 1
            payload = json.loads(request.content.decode("utf-8"))
            assert payload == payload_dump
            return httpx.Response(
                200,
                json={
                    "outputId": output_id,
                    "inputId": str(input_file.id),
                },
            )
        if request.method == "GET" and request.url.path == f"/resource/{output_id}":
            seen["get"] += 1
            return httpx.Response(
                200,
                json=build_file_info_payload(output_id, "summary.txt", "text/plain"),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.summarize_pdf_text_to_file(
            input_file,
            target_word_count=200,
            summary_format="bullet_points",
            pages=["2-last"],
            output_format="plaintext",
            output="summary",
        )

    assert seen == {"post": 1, "get": 1}
    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.output_file.id == output_id
    assert response.output_file.name == "summary.txt"
    assert response.input_id == input_file.id


def test_summarize_pdf_text_to_file_request_customization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(1))
    payload_dump = SummarizePdfTextPayload.model_validate(
        {
            "files": [input_file],
            "output_type": "file",
            "output_format": "markdown",
            "summary_format": "overview",
        }
    ).model_dump(mode="json", by_alias=True, exclude_none=True, exclude_unset=True)
    output_id = str(PdfRestFileID.generate())

    captured_timeout: dict[str, float | dict[str, float] | None] = {}
    seen: dict[str, int] = {"post": 0, "get": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/summarized-pdf-text":
            seen["post"] += 1
            assert request.url.params["trace"] == "true"
            assert request.headers["X-Debug"] == "sync"
            captured_timeout["value"] = request.extensions.get("timeout")
            payload = json.loads(request.content.decode("utf-8"))
            for key, value in payload_dump.items():
                assert payload[key] == value
            assert payload["debug"] is True
            return httpx.Response(
                200,
                json={
                    "outputId": output_id,
                    "inputId": str(input_file.id),
                },
            )
        if request.method == "GET" and request.url.path == f"/resource/{output_id}":
            seen["get"] += 1
            assert request.url.params["format"] == "info"
            assert request.url.params["trace"] == "true"
            assert request.headers["X-Debug"] == "sync"
            return httpx.Response(
                200,
                json=build_file_info_payload(output_id, "summary.txt", "text/plain"),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.summarize_pdf_text_to_file(
            input_file,
            extra_query={"trace": "true"},
            extra_headers={"X-Debug": "sync"},
            extra_body={"debug": True},
            timeout=0.25,
        )

    assert seen == {"post": 1, "get": 1}
    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.output_file.id == output_id
    assert response.output_file.name == "summary.txt"
    timeout_value = captured_timeout["value"]
    assert timeout_value is not None
    if isinstance(timeout_value, dict):
        assert all(
            component == pytest.approx(0.25) for component in timeout_value.values()
        )
    else:
        assert timeout_value == pytest.approx(0.25)


@pytest.mark.asyncio
async def test_async_summarize_pdf_text_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(2))
    payload_dump = SummarizePdfTextPayload.model_validate(
        {"files": [input_file], "output_type": "json"}
    ).model_dump(mode="json", by_alias=True, exclude_none=True, exclude_unset=True)

    seen: dict[str, int] = {"post": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/summarized-pdf-text":
            seen["post"] += 1
            payload = json.loads(request.content.decode("utf-8"))
            for key, value in payload_dump.items():
                assert payload[key] == value
            return httpx.Response(
                200,
                json={
                    "summary": "Async summary",
                    "inputId": str(input_file.id),
                },
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        response = await client.summarize_pdf_text(input_file)

    assert seen == {"post": 1}
    assert isinstance(response, SummarizePdfTextResponse)
    assert response.summary == "Async summary"
    assert response.input_id == input_file.id


@pytest.mark.asyncio
async def test_async_summarize_pdf_text_to_file_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(2))
    payload_dump = SummarizePdfTextPayload.model_validate(
        {"files": [input_file], "output_type": "file"}
    ).model_dump(mode="json", by_alias=True, exclude_none=True, exclude_unset=True)
    output_id = str(PdfRestFileID.generate())

    seen: dict[str, int] = {"post": 0, "get": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/summarized-pdf-text":
            seen["post"] += 1
            payload = json.loads(request.content.decode("utf-8"))
            for key, value in payload_dump.items():
                assert payload[key] == value
            return httpx.Response(
                200,
                json={
                    "outputId": output_id,
                    "inputId": str(input_file.id),
                },
            )
        if request.method == "GET" and request.url.path == f"/resource/{output_id}":
            seen["get"] += 1
            return httpx.Response(
                200,
                json=build_file_info_payload(
                    output_id, "async-summary.txt", "text/plain"
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        response = await client.summarize_pdf_text_to_file(input_file)

    assert seen == {"post": 1, "get": 1}
    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.output_file.id == output_id
    assert response.input_id == input_file.id
