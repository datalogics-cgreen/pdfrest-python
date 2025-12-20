from __future__ import annotations

import json

import httpx
import pytest
from pydantic import ValidationError

from pdfrest import AsyncPdfRestClient, PdfRestClient
from pdfrest.models import ConvertToMarkdownResponse, PdfRestFile, PdfRestFileID
from pdfrest.models._internal import ConvertToMarkdownPayload

from .graphics_test_helpers import ASYNC_API_KEY, VALID_API_KEY, make_pdf_file


def test_convert_to_markdown_payload_rejects_non_pdf() -> None:
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
        ConvertToMarkdownPayload.model_validate({"files": [text_file]})


def test_convert_to_markdown_payload_invalid_page_range() -> None:
    file_repr = make_pdf_file(PdfRestFileID.generate(1))
    with pytest.raises(
        ValidationError, match="The start page must be less than or equal to the end"
    ):
        ConvertToMarkdownPayload.model_validate(
            {"files": [file_repr], "pages": ["5-2"]}
        )


def test_convert_to_markdown_payload_invalid_page_break_comments() -> None:
    file_repr = make_pdf_file(PdfRestFileID.generate(1))
    with pytest.raises(ValidationError, match="Input should be 'on' or 'off'"):
        ConvertToMarkdownPayload.model_validate(
            {"files": [file_repr], "page_break_comments": "maybe"}
        )


def test_convert_to_markdown_json_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(1))
    payload_dump = ConvertToMarkdownPayload.model_validate(
        {
            "files": [input_file],
            "pages": ["1-3"],
            "output": "md",
            "output_type": "json",
            "page_break_comments": "on",
        }
    ).model_dump(mode="json", by_alias=True, exclude_none=True, exclude_unset=True)

    seen: dict[str, int] = {"post": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/markdown":
            seen["post"] += 1
            payload = json.loads(request.content.decode("utf-8"))
            for key, value in payload_dump.items():
                assert payload[key] == value
            return httpx.Response(
                200,
                json={
                    "markdown": "# Title",
                    "inputId": str(input_file.id),
                },
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.convert_to_markdown(
            input_file,
            pages=["1-3"],
            output="md",
            output_type="json",
            page_break_comments="on",
        )

    assert seen == {"post": 1}
    assert isinstance(response, ConvertToMarkdownResponse)
    assert response.markdown == "# Title"
    assert response.input_id == input_file.id
    assert response.output_id is None
    assert response.output_url is None


def test_convert_to_markdown_request_customization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(1))
    payload_dump = ConvertToMarkdownPayload.model_validate(
        {
            "files": [input_file],
            "output_type": "file",
            "page_break_comments": "off",
        }
    ).model_dump(mode="json", by_alias=True, exclude_none=True, exclude_unset=True)
    output_id = str(PdfRestFileID.generate())
    captured_timeout: dict[str, float | dict[str, float] | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/markdown":
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
                    "outputUrl": f"https://api.pdfrest.com/resource/{output_id}?format=file",
                    "outputId": output_id,
                    "inputId": str(input_file.id),
                },
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.convert_to_markdown(
            input_file,
            output_type="file",
            extra_query={"trace": "true"},
            extra_headers={"X-Debug": "sync"},
            extra_body={"debug": True},
            timeout=0.4,
            page_break_comments="off",
        )

    assert isinstance(response, ConvertToMarkdownResponse)
    assert response.output_id == output_id
    assert response.output_url
    timeout_value = captured_timeout["value"]
    assert timeout_value is not None
    if isinstance(timeout_value, dict):
        assert all(
            component == pytest.approx(0.4) for component in timeout_value.values()
        )
    else:
        assert timeout_value == pytest.approx(0.4)


@pytest.mark.asyncio
async def test_async_convert_to_markdown_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(2))
    payload_dump = ConvertToMarkdownPayload.model_validate(
        {"files": [input_file], "output_type": "json", "page_break_comments": "off"}
    ).model_dump(mode="json", by_alias=True, exclude_none=True, exclude_unset=True)

    seen: dict[str, int] = {"post": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/markdown":
            seen["post"] += 1
            payload = json.loads(request.content.decode("utf-8"))
            for key, value in payload_dump.items():
                assert payload[key] == value
            return httpx.Response(
                200,
                json={
                    "markdown": "Async md",
                    "inputId": str(input_file.id),
                },
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        response = await client.convert_to_markdown(
            input_file, output_type="json", page_break_comments="off"
        )

    assert seen == {"post": 1}
    assert isinstance(response, ConvertToMarkdownResponse)
    assert response.markdown == "Async md"
    assert response.input_id == input_file.id
