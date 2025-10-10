from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import httpx
import pytest

from pdfrest import AsyncPdfRestClient, PdfRestClient
from pdfrest.models import PdfRestFile

from .resources import get_test_resource_path

VALID_API_KEY = "12345678-1234-1234-1234-123456789abc"


def _build_file_info_payload(file_id: str, name: str) -> dict[str, Any]:
    return {
        "id": file_id,
        "name": name,
        "url": f"https://api.pdfrest.com/resource/{file_id}",
        "type": "application/pdf"
        if name.endswith(".pdf")
        else "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "size": 1,
        "modified": datetime(2024, 1, 1, tzinfo=timezone.utc)
        .isoformat()
        .replace("+00:00", "Z"),
        "scheduledDeletionTimeUtc": None,
    }


def test_files_create_uses_upload_and_info() -> None:
    uploaded_file_id = str(uuid.uuid4())
    info_payload = _build_file_info_payload(uploaded_file_id, "report.pdf")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/upload":
            return httpx.Response(
                200,
                json={
                    "files": [
                        {"name": "report.pdf", "id": uploaded_file_id},
                    ]
                },
            )
        if (
            request.method == "GET"
            and request.url.path == f"/resource/{uploaded_file_id}"
        ):
            assert request.url.params["format"] == "info"
            return httpx.Response(200, json=info_payload)
        msg = f"Unexpected request: {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    client = PdfRestClient(api_key=VALID_API_KEY, transport=transport)
    report_pdf = get_test_resource_path("report.pdf")
    try:
        with report_pdf.open("rb") as pdf_file:
            response = client.files.create([pdf_file])
    finally:
        client.close()

    assert isinstance(response, list)
    assert len(response) == 1
    file_repr = response[0]
    assert isinstance(file_repr, PdfRestFile)
    assert file_repr.id == uploaded_file_id
    assert file_repr.name == "report.pdf"
    assert str(file_repr.url).endswith(uploaded_file_id)


@pytest.mark.asyncio
async def test_async_files_create_uses_upload_and_info() -> None:
    uploaded_ids = [str(uuid.uuid4()), str(uuid.uuid4())]
    info_payloads = {
        uploaded_ids[0]: _build_file_info_payload(uploaded_ids[0], "report.pdf"),
        uploaded_ids[1]: _build_file_info_payload(uploaded_ids[1], "report.docx"),
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/upload":
            return httpx.Response(
                200,
                json={
                    "files": [
                        {"name": "report.pdf", "id": uploaded_ids[0]},
                        {"name": "report.docx", "id": uploaded_ids[1]},
                    ]
                },
            )
        if request.method == "GET" and request.url.path.startswith("/resource/"):
            file_id = request.url.path.split("/")[-1]
            assert request.url.params["format"] == "info"
            payload = info_payloads[file_id]
            return httpx.Response(200, json=payload)
        msg = f"Unexpected request: {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    client = AsyncPdfRestClient(api_key=VALID_API_KEY, transport=transport)

    report_pdf = get_test_resource_path("report.pdf")
    report_docx = get_test_resource_path("report.docx")
    async with client:
        with report_pdf.open("rb") as pdf_file, report_docx.open("rb") as docx_file:
            response = await client.files.create([pdf_file, docx_file])

    assert isinstance(response, list)
    assert len(response) == 2
    for file_repr, file_id in zip(response, uploaded_ids, strict=True):
        assert isinstance(file_repr, PdfRestFile)
        assert file_repr.id == file_id


def test_live_file_create(pdfrest_api_key: str, pdfrest_live_base_url: str) -> None:
    with PdfRestClient(
        api_key=pdfrest_api_key, base_url=pdfrest_live_base_url
    ) as client:
        report_pdf = get_test_resource_path("report.pdf")
        with report_pdf.open("rb") as pdf_file:
            response = client.files.create([pdf_file])
            assert isinstance(response, list)
            assert len(response) == 1
            assert isinstance(response[0], PdfRestFile)


def test_live_file_create_two_files(
    pdfrest_api_key: str, pdfrest_live_base_url: str
) -> None:
    with PdfRestClient(
        api_key=pdfrest_api_key, base_url=pdfrest_live_base_url
    ) as client:
        report_pdf = get_test_resource_path("report.pdf")
        report_docx = get_test_resource_path("report.docx")
        with report_pdf.open("rb") as pdf_file, report_docx.open("rb") as docx_file:
            response = client.files.create([pdf_file, docx_file])
            assert isinstance(response, list)
            assert len(response) == 2
            assert isinstance(response[0], PdfRestFile)
            assert isinstance(response[1], PdfRestFile)
