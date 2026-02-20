from __future__ import annotations

import json

import httpx
import pytest
from pydantic import ValidationError
from pydantic_core import to_json

from pdfrest import AsyncPdfRestClient, PdfRestClient
from pdfrest.models import PdfRestFileBasedResponse, PdfRestFileID
from pdfrest.models._internal import PdfRedactionPreviewPayload
from pdfrest.types import PdfRedactionInstruction

from .graphics_test_helpers import (
    ASYNC_API_KEY,
    VALID_API_KEY,
    build_file_info_payload,
    make_pdf_file,
)


@pytest.mark.parametrize(
    "redactions",
    [
        pytest.param(
            [
                {"type": "literal", "value": "Sensitive"},
                {"type": "preset", "value": "email"},
            ],
            id="list",
        ),
        pytest.param({"type": "regex", "value": "\\d{3}-\\d{2}-\\d{4}"}, id="single"),
    ],
)
def test_preview_redactions_success(
    monkeypatch: pytest.MonkeyPatch,
    redactions: PdfRedactionInstruction | list[PdfRedactionInstruction],
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(1))
    output_id = str(PdfRestFileID.generate())
    payload_model_dump = PdfRedactionPreviewPayload.model_validate(
        {
            "files": [input_file],
            "redactions": redactions,
            "output": "preview-output",
        }
    ).model_dump(mode="json", by_alias=True, exclude_none=True, exclude_unset=True)

    def handler(request: httpx.Request) -> httpx.Response:
        if (
            request.method == "POST"
            and request.url.path == "/pdf-with-redacted-text-preview"
        ):
            body = json.loads(request.content.decode("utf-8"))
            assert body == payload_model_dump
            return httpx.Response(
                200,
                json={
                    "inputId": [input_file.id],
                    "outputId": [output_id],
                },
            )
        if request.method == "GET" and request.url.path == f"/resource/{output_id}":
            return httpx.Response(
                200,
                json=build_file_info_payload(
                    output_id, "preview-output.pdf", "application/pdf"
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.preview_redactions(
            input_file,
            redactions=redactions,
            output="preview-output",
        )

    assert isinstance(response, PdfRestFileBasedResponse)
    assert str(response.input_id) == str(input_file.id)
    assert response.output_files[0].name == "preview-output.pdf"
    assert response.output_files[0].type == "application/pdf"
    assert response.warning is None


def test_preview_redactions_invalid_preset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(1))
    transport = httpx.MockTransport(lambda request: (_ for _ in ()).throw(RuntimeError))

    with (
        PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client,
        pytest.raises(ValidationError, match="Input should be 'email'"),
    ):
        client.preview_redactions(
            input_file,
            redactions=[{"type": "preset", "value": "unknown"}],
        )


def test_preview_redactions_reject_json_string(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(1))
    transport = httpx.MockTransport(lambda request: (_ for _ in ()).throw(RuntimeError))

    with (
        PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client,
        pytest.raises(ValidationError, match="valid dictionary"),
    ):
        client.preview_redactions(
            input_file,
            redactions=to_json([{"type": "literal", "value": "secret"}]).decode(),  # type: ignore[arg-type]
        )


def test_preview_redactions_requires_instruction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(1))
    transport = httpx.MockTransport(lambda request: (_ for _ in ()).throw(RuntimeError))

    with (
        PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client,
        pytest.raises(ValidationError, match="at least 1 item"),
    ):
        client.preview_redactions(input_file, redactions=[])


@pytest.mark.asyncio
async def test_async_preview_redactions_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(1))
    output_id = str(PdfRestFileID.generate())
    redactions: list[PdfRedactionInstruction] = [
        {"type": "literal", "value": "Sensitive"}
    ]

    payload_model_dump = PdfRedactionPreviewPayload.model_validate(
        {
            "files": [input_file],
            "redactions": redactions,
            "output": "preview-output-async",
        }
    ).model_dump(mode="json", by_alias=True, exclude_none=True, exclude_unset=True)

    def handler(request: httpx.Request) -> httpx.Response:
        if (
            request.method == "POST"
            and request.url.path == "/pdf-with-redacted-text-preview"
        ):
            body = json.loads(request.content.decode("utf-8"))
            assert body == payload_model_dump
            return httpx.Response(
                200,
                json={
                    "inputId": [input_file.id],
                    "outputId": [output_id],
                },
            )
        if request.method == "GET" and request.url.path == f"/resource/{output_id}":
            return httpx.Response(
                200,
                json=build_file_info_payload(
                    output_id, "preview-output-async.pdf", "application/pdf"
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        response = await client.preview_redactions(
            input_file,
            redactions=redactions,
            output="preview-output-async",
        )

    assert isinstance(response, PdfRestFileBasedResponse)
    assert str(response.input_id) == str(input_file.id)
    assert response.output_files[0].name == "preview-output-async.pdf"
    assert response.output_files[0].type == "application/pdf"
    assert response.warning is None
