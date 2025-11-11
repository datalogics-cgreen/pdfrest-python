from __future__ import annotations

import json

import httpx
import pytest
from pydantic import ValidationError

from pdfrest import AsyncPdfRestClient, PdfRestClient
from pdfrest.models import PdfRestFileBasedResponse, PdfRestFileID
from pdfrest.models._internal import PdfMergePayload
from pdfrest.types import PdfMergeInput

from .graphics_test_helpers import (
    ASYNC_API_KEY,
    VALID_API_KEY,
    build_file_info_payload,
    make_pdf_file,
)


def test_merge_pdfs_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    source_a = make_pdf_file(PdfRestFileID.generate(1), name="a.pdf")
    source_b = make_pdf_file(PdfRestFileID.generate(1), name="b.pdf")
    source_c = make_pdf_file(PdfRestFileID.generate(1), name="c.pdf")
    output_id = str(PdfRestFileID.generate())

    merge_sources: list[PdfMergeInput] = [
        {"file": source_a, "pages": "even"},
        source_b,
        (source_c, ("9-2", "odd")),
    ]

    pdf_merge_payload = PdfMergePayload.model_validate(
        {
            "sources": merge_sources,
            "output_prefix": "merged-output",
        }
    )
    request_payload = pdf_merge_payload.model_dump(
        mode="json", by_alias=True, exclude_none=True, exclude_unset=True
    )

    seen: dict[str, int] = {"post": 0, "get": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/merged-pdf":
            seen["post"] += 1
            payload = json.loads(request.content.decode("utf-8"))
            assert payload == request_payload
            return httpx.Response(
                200,
                json={
                    "inputId": [source_a.id, source_b.id, source_c.id],
                    "outputId": output_id,
                },
            )
        if request.method == "GET" and request.url.path == f"/resource/{output_id}":
            seen["get"] += 1
            return httpx.Response(
                200,
                json=build_file_info_payload(
                    output_id, "merged-output.pdf", "application/pdf"
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.merge_pdfs(merge_sources, output_prefix="merged-output")

    assert seen == {"post": 1, "get": 1}
    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.output_file.name == "merged-output.pdf"
    assert response.output_file.type == "application/pdf"
    assert len(response.input_ids) == 3
    assert {str(input_id) for input_id in response.input_ids} == {
        str(source_a.id),
        str(source_b.id),
        str(source_c.id),
    }
    assert response.warning is None


def test_merge_pdfs_requires_multiple_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    single_source = make_pdf_file(PdfRestFileID.generate(1))
    transport = httpx.MockTransport(lambda request: (_ for _ in ()).throw(RuntimeError))

    with (
        PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client,
        pytest.raises(ValidationError, match="at least 2"),
    ):
        client.merge_pdfs([single_source])


def test_merge_pdfs_invalid_page_range(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    source_a = make_pdf_file(PdfRestFileID.generate(1))
    source_b = make_pdf_file(PdfRestFileID.generate(1))
    transport = httpx.MockTransport(lambda request: (_ for _ in ()).throw(RuntimeError))

    with (
        PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client,
        pytest.raises(ValidationError, match="greater than or equal to 1"),
    ):
        client.merge_pdfs([source_a, (source_b, 0)])


@pytest.mark.asyncio
async def test_async_merge_pdfs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    source_a = make_pdf_file(PdfRestFileID.generate(1))
    source_b = make_pdf_file(PdfRestFileID.generate(1))
    output_id = str(PdfRestFileID.generate())

    request_payload = PdfMergePayload.model_validate(
        {
            "sources": [source_a, {"file": source_b, "pages": "2-last"}],
            "output_prefix": "async-merge",
        }
    ).model_dump(mode="json", by_alias=True, exclude_none=True, exclude_unset=True)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/merged-pdf":
            payload = json.loads(request.content.decode("utf-8"))
            assert payload == request_payload
            return httpx.Response(
                200,
                json={
                    "inputId": [source_a.id, source_b.id],
                    "outputId": output_id,
                },
            )
        if request.method == "GET" and request.url.path == f"/resource/{output_id}":
            return httpx.Response(
                200,
                json=build_file_info_payload(
                    output_id, "async-merge.pdf", "application/pdf"
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        response = await client.merge_pdfs(
            [source_a, {"file": source_b, "pages": "2-last"}],
            output_prefix="async-merge",
        )

    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.output_file.name == "async-merge.pdf"
