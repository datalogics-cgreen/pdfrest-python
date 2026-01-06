from __future__ import annotations

import json

import httpx
import pytest
from pydantic import ValidationError

from pdfrest import AsyncPdfRestClient, PdfRestClient
from pdfrest.models import (
    PdfRestFile,
    PdfRestFileID,
    TranslatePdfTextFileResponse,
    TranslatePdfTextResponse,
)
from pdfrest.models._internal import TranslatePdfTextPayload

from .graphics_test_helpers import ASYNC_API_KEY, VALID_API_KEY, make_pdf_file


def _make_markdown_file(file_id: str) -> PdfRestFile:
    return PdfRestFile.model_validate(
        {
            "id": file_id,
            "name": "notes.md",
            "url": f"https://api.pdfrest.com/resource/{file_id}",
            "type": "text/markdown",
            "size": 64,
            "modified": "2024-01-01T00:00:00Z",
            "scheduledDeletionTimeUtc": None,
        }
    )


def test_translate_payload_rejects_invalid_mime() -> None:
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
        TranslatePdfTextPayload.model_validate(
            {"files": [image_file], "output_language": "fr"}
        )


def test_translate_payload_requires_target_language() -> None:
    file_repr = make_pdf_file(PdfRestFileID.generate(1))
    with pytest.raises(ValidationError):
        TranslatePdfTextPayload.model_validate({"files": [file_repr]})


def test_translate_pdf_text_json_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = _make_markdown_file(str(PdfRestFileID.generate(1)))
    payload_dump = TranslatePdfTextPayload.model_validate(
        {
            "files": [input_file],
            "output_language": "fr",
            "pages": ["1-2"],
            "output_format": "plaintext",
            "output_type": "json",
            "output": "translation",
        }
    ).model_dump(mode="json", by_alias=True, exclude_none=True, exclude_unset=True)

    seen: dict[str, int] = {"post": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/translated-pdf-text":
            seen["post"] += 1
            payload = json.loads(request.content.decode("utf-8"))
            assert payload == payload_dump
            return httpx.Response(
                200,
                json={
                    "translated_text": "Bonjour",
                    "inputId": str(input_file.id),
                    "source_languages": ["en"],
                    "output_language": "fr",
                },
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.translate_pdf_text(
            input_file,
            output_language="fr",
            pages=["1-2"],
            output_format="plaintext",
            output="translation",
        )

    assert seen == {"post": 1}
    assert isinstance(response, TranslatePdfTextResponse)
    assert response.translated_text == "Bonjour"
    assert response.source_languages == ["en"]
    assert response.output_language == "fr"
    assert response.input_id == input_file.id
    assert response.output_id is None
    assert response.output_url is None


def test_translate_pdf_text_request_customization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(1))
    payload_dump = TranslatePdfTextPayload.model_validate(
        {
            "files": [input_file],
            "output_language": "es",
            "output_type": "file",
        }
    ).model_dump(mode="json", by_alias=True, exclude_none=True, exclude_unset=True)
    output_id = str(PdfRestFileID.generate())

    captured_timeout: dict[str, float | dict[str, float] | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/translated-pdf-text":
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
                    "source_languages": ["en"],
                    "output_language": "es",
                },
            )
        if request.method == "GET" and request.url.path == f"/resource/{output_id}":
            assert request.url.params["format"] == "info"
            assert request.url.params["trace"] == "true"
            assert request.headers["X-Debug"] == "sync"
            return httpx.Response(
                200,
                json=_make_markdown_file(output_id).model_dump(
                    mode="json", by_alias=True
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.translate_pdf_text_to_file(
            input_file,
            output_language="es",
            extra_query={"trace": "true"},
            extra_headers={"X-Debug": "sync"},
            extra_body={"debug": True},
            timeout=0.3,
        )

    assert isinstance(response, TranslatePdfTextFileResponse)
    assert response.output_file.id == output_id
    assert response.output_language == "es"
    assert response.source_languages == ["en"]
    timeout_value = captured_timeout["value"]
    assert timeout_value is not None
    if isinstance(timeout_value, dict):
        assert all(
            component == pytest.approx(0.3) for component in timeout_value.values()
        )
    else:
        assert timeout_value == pytest.approx(0.3)


@pytest.mark.asyncio
async def test_async_translate_pdf_text_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(2))
    payload_dump = TranslatePdfTextPayload.model_validate(
        {"files": [input_file], "output_language": "de", "output_type": "json"}
    ).model_dump(mode="json", by_alias=True, exclude_none=True, exclude_unset=True)

    seen: dict[str, int] = {"post": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/translated-pdf-text":
            seen["post"] += 1
            payload = json.loads(request.content.decode("utf-8"))
            for key, value in payload_dump.items():
                assert payload[key] == value
            return httpx.Response(
                200,
                json={
                    "translated_text": "Hallo",
                    "inputId": str(input_file.id),
                    "source_languages": ["en"],
                    "output_language": "de",
                },
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        response = await client.translate_pdf_text(
            input_file,
            output_language="de",
        )

    assert seen == {"post": 1}
    assert isinstance(response, TranslatePdfTextResponse)
    assert response.translated_text == "Hallo"
    assert response.source_languages == ["en"]
    assert response.output_language == "de"
    assert response.input_id == input_file.id
