from __future__ import annotations

import json

import httpx
import pytest
from pydantic import ValidationError

from pdfrest import AsyncPdfRestClient, PdfRestClient
from pdfrest.models import PdfRestFileBasedResponse, PdfRestFileID
from pdfrest.models._internal import PdfSplitPayload

from .graphics_test_helpers import (
    ASYNC_API_KEY,
    VALID_API_KEY,
    build_file_info_payload,
    make_pdf_file,
)


def test_split_pdf_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(1))
    output_ids = [str(PdfRestFileID.generate()) for _ in range(4)]
    page_groups: list[str | list[int | str]] = [
        ["1", "2-4", 5, "6-last"],
        "even",
        "9-2",
        "odd",
    ]

    request_payload = PdfSplitPayload.model_validate(
        {
            "files": [input_file],
            "page_groups": page_groups,
            "output_prefix": "split-output",
        }
    ).model_dump(mode="json", by_alias=True, exclude_none=True, exclude_unset=True)

    seen: dict[str, int] = {"post": 0, "get": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/split-pdf":
            seen["post"] += 1
            payload = json.loads(request.content.decode("utf-8"))
            assert payload == request_payload
            return httpx.Response(
                200,
                json={
                    "inputId": [input_file.id],
                    "outputId": output_ids,
                },
            )
        if request.method == "GET" and request.url.path in {
            f"/resource/{identifier}" for identifier in output_ids
        }:
            seen["get"] += 1
            file_id = request.url.path.split("/")[-1]
            index = output_ids.index(file_id) + 1
            name = f"split-output-{index:03d}.pdf"
            return httpx.Response(
                200,
                json=build_file_info_payload(file_id, name, "application/pdf"),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.split_pdf(
            input_file,
            page_groups=page_groups,
            output_prefix="split-output",
        )

    assert seen["post"] == 1
    assert seen["get"] == len(output_ids)
    assert isinstance(response, PdfRestFileBasedResponse)
    assert len(response.output_files) == len(output_ids)
    expected_names = [
        f"split-output-{idx:03d}.pdf" for idx in range(1, len(output_ids) + 1)
    ]
    assert [output_file.name for output_file in response.output_files] == expected_names
    assert [output_file.type for output_file in response.output_files] == [
        "application/pdf"
    ] * len(output_ids)
    assert str(response.input_id) == str(input_file.id)
    assert response.warning is None


def test_split_pdf_without_page_groups(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(1))
    output_ids = [str(PdfRestFileID.generate()) for _ in range(3)]

    request_payload = PdfSplitPayload.model_validate(
        {
            "files": [input_file],
        }
    ).model_dump(mode="json", by_alias=True, exclude_none=True, exclude_unset=True)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/split-pdf":
            payload = json.loads(request.content.decode("utf-8"))
            assert payload == request_payload
            return httpx.Response(
                200,
                json={
                    "inputId": [input_file.id],
                    "outputId": output_ids,
                },
            )
        if request.method == "GET" and request.url.path in {
            f"/resource/{identifier}" for identifier in output_ids
        }:
            file_id = request.url.path.split("/")[-1]
            index = output_ids.index(file_id) + 1
            return httpx.Response(
                200,
                json=build_file_info_payload(
                    file_id,
                    f"auto-split-{index:03d}.pdf",
                    "application/pdf",
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.split_pdf(input_file)

    assert isinstance(response, PdfRestFileBasedResponse)
    assert len(response.output_files) == len(output_ids)
    assert [file.name for file in response.output_files] == [
        f"auto-split-{idx:03d}.pdf" for idx in range(1, len(output_ids) + 1)
    ]
    assert all(file.type == "application/pdf" for file in response.output_files)


def test_split_pdf_invalid_page_group(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(1))
    transport = httpx.MockTransport(lambda request: (_ for _ in ()).throw(RuntimeError))

    with (
        PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client,
        pytest.raises(ValidationError, match="greater than or equal to 1"),
    ):
        client.split_pdf(input_file, page_groups=["0"])


@pytest.mark.asyncio
async def test_async_split_pdf(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(1))
    output_id = str(PdfRestFileID.generate())

    request_payload = PdfSplitPayload.model_validate(
        {
            "files": [input_file],
            "page_groups": ["1-2"],
            "output_prefix": "async-split",
        }
    ).model_dump(mode="json", by_alias=True, exclude_none=True, exclude_unset=True)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/split-pdf":
            payload = json.loads(request.content.decode("utf-8"))
            assert payload == request_payload
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
                    output_id, "async-split-001.pdf", "application/pdf"
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        response = await client.split_pdf(
            input_file,
            page_groups=["1-2"],
            output_prefix="async-split",
        )

    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.output_files[0].name == "async-split-001.pdf"
