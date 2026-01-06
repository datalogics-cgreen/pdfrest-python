from __future__ import annotations

import json

import httpx
import pytest
from pydantic import ValidationError

from pdfrest import AsyncPdfRestClient, PdfRestClient
from pdfrest.models import PdfRestFile, PdfRestFileBasedResponse, PdfRestFileID
from pdfrest.models._internal import ExtractTextPayload

from .graphics_test_helpers import ASYNC_API_KEY, VALID_API_KEY, make_pdf_file


def _make_text_file(file_id: str, name: str = "extracted.txt") -> PdfRestFile:
    return PdfRestFile.model_validate(
        {
            "id": file_id,
            "name": name,
            "url": f"https://api.pdfrest.com/resource/{file_id}",
            "type": "text/plain",
            "size": 64,
            "modified": "2024-01-01T00:00:00Z",
            "scheduledDeletionTimeUtc": None,
        }
    )


def test_extract_pdf_text_payload_rejects_non_pdf() -> None:
    file_id = str(PdfRestFileID.generate())
    text_file = PdfRestFile.model_validate(
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
    with pytest.raises(ValidationError, match="Must be a PDF file"):
        ExtractTextPayload.model_validate({"files": [text_file]})


def test_extract_pdf_text_payload_invalid_page_range() -> None:
    file_repr = make_pdf_file(PdfRestFileID.generate(1))
    with pytest.raises(
        ValidationError, match="The start page must be less than or equal to the end"
    ):
        ExtractTextPayload.model_validate({"files": [file_repr], "pages": ["5-2"]})


def test_extract_pdf_text_to_file_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(1))
    output_id = str(PdfRestFileID.generate())
    payload_dump = ExtractTextPayload.model_validate(
        {
            "files": [input_file],
            "pages": ["1-3"],
            "output": "text",
            "full_text": "document",
            "preserve_line_breaks": "off",
            "word_style": "off",
            "word_coordinates": "off",
            "output_type": "file",
        }
    ).model_dump(mode="json", by_alias=True, exclude_none=True, exclude_unset=True)

    seen: dict[str, int] = {"post": 0, "get": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/extracted-text":
            seen["post"] += 1
            payload = json.loads(request.content.decode("utf-8"))
            assert payload == payload_dump
            return httpx.Response(
                200,
                json={
                    "inputId": [str(input_file.id)],
                    "outputId": [output_id],
                },
            )
        if request.method == "GET" and request.url.path == f"/resource/{output_id}":
            seen["get"] += 1
            assert request.url.params["format"] == "info"
            return httpx.Response(
                200,
                json=_make_text_file(output_id).model_dump(mode="json", by_alias=True),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.extract_pdf_text_to_file(
            input_file,
            pages=["1-3"],
            output="text",
        )

    assert seen == {"post": 1, "get": 1}
    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.input_id == input_file.id
    assert len(response.output_files) == 1
    assert response.output_file.id == output_id


def test_extract_pdf_text_request_customization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(1))
    output_id = str(PdfRestFileID.generate())
    payload_dump = ExtractTextPayload.model_validate(
        {
            "files": [input_file],
            "output": "file-output",
            "full_text": "document",
            "preserve_line_breaks": "off",
            "word_style": "off",
            "word_coordinates": "off",
            "output_type": "file",
        }
    ).model_dump(mode="json", by_alias=True, exclude_none=True, exclude_unset=True)
    captured_timeout: dict[str, float | dict[str, float] | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/extracted-text":
            assert request.url.params["trace"] == "true"
            assert request.headers["X-Debug"] == "sync"
            captured_timeout["post"] = request.extensions.get("timeout")
            payload = json.loads(request.content.decode("utf-8"))
            assert payload == payload_dump | {"debug": True}
            return httpx.Response(
                200,
                json={
                    "inputId": [str(input_file.id)],
                    "outputId": [output_id],
                },
            )
        if request.method == "GET" and request.url.path == f"/resource/{output_id}":
            assert request.url.params["format"] == "info"
            assert request.url.params["trace"] == "true"
            assert request.headers["X-Debug"] == "sync"
            captured_timeout["get"] = request.extensions.get("timeout")
            return httpx.Response(
                200,
                json=_make_text_file(output_id, "debug.txt").model_dump(
                    mode="json", by_alias=True
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.extract_pdf_text_to_file(
            input_file,
            output="file-output",
            extra_query={"trace": "true"},
            extra_headers={"X-Debug": "sync"},
            extra_body={"debug": True},
            timeout=0.35,
        )

    assert isinstance(response, PdfRestFileBasedResponse)
    assert len(response.output_files) == 1
    post_timeout = captured_timeout["post"]
    get_timeout = captured_timeout["get"]
    assert post_timeout is not None
    assert get_timeout is not None
    if isinstance(post_timeout, dict):
        assert all(
            component == pytest.approx(0.35) for component in post_timeout.values()
        )
    else:
        assert post_timeout == pytest.approx(0.35)
    if isinstance(get_timeout, dict):
        assert all(
            component == pytest.approx(0.35) for component in get_timeout.values()
        )
    else:
        assert get_timeout == pytest.approx(0.35)


@pytest.mark.asyncio
async def test_async_extract_pdf_text_to_file_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(2))
    output_id = str(PdfRestFileID.generate())
    payload_dump = ExtractTextPayload.model_validate(
        {
            "files": [input_file],
            "full_text": "document",
            "preserve_line_breaks": "off",
            "word_style": "off",
            "word_coordinates": "off",
            "output_type": "file",
        }
    ).model_dump(mode="json", by_alias=True, exclude_none=True, exclude_unset=True)

    seen: dict[str, int] = {"post": 0, "get": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/extracted-text":
            seen["post"] += 1
            payload = json.loads(request.content.decode("utf-8"))
            assert payload == payload_dump
            return httpx.Response(
                200,
                json={
                    "inputId": [str(input_file.id)],
                    "outputId": [output_id],
                },
            )
        if request.method == "GET" and request.url.path == f"/resource/{output_id}":
            seen["get"] += 1
            assert request.url.params["format"] == "info"
            return httpx.Response(
                200,
                json=_make_text_file(output_id, "async.txt").model_dump(
                    mode="json", by_alias=True
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        response = await client.extract_pdf_text_to_file(input_file)

    assert seen == {"post": 1, "get": 1}
    assert isinstance(response, PdfRestFileBasedResponse)
    assert len(response.output_files) == 1
    assert response.input_id == input_file.id
