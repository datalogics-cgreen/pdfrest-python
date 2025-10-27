from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, cast

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


def _iso_to_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _assert_file_matches_payload(
    file_repr: PdfRestFile, expected_payload: dict[str, Any]
) -> None:
    assert isinstance(file_repr, PdfRestFile)
    assert file_repr.id == expected_payload["id"]
    assert file_repr.name == expected_payload["name"]
    assert str(file_repr.url) == expected_payload["url"]
    assert file_repr.type == expected_payload["type"]
    assert file_repr.size == expected_payload["size"]
    assert file_repr.modified == _iso_to_datetime(expected_payload["modified"])
    assert file_repr.scheduled_deletion_time_utc is None


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
            response = client.files.create([("report.pdf", pdf_file)])
    finally:
        client.close()

    assert isinstance(response, list)
    assert len(response) == 1
    file_repr = response[0]
    assert isinstance(file_repr, PdfRestFile)
    _assert_file_matches_payload(file_repr, info_payload)


def test_files_create_from_paths_uses_upload_and_info() -> None:
    uploaded_ids = [str(uuid.uuid4()), str(uuid.uuid4())]
    info_payloads = {
        uploaded_ids[0]: _build_file_info_payload(uploaded_ids[0], "report.pdf"),
        uploaded_ids[1]: _build_file_info_payload(uploaded_ids[1], "report.docx"),
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/upload":
            body = request.content
            assert body.count(b'name="file"') == 2
            assert b'filename="report.pdf"' in body
            assert b'filename="report.docx"' in body
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
    client = PdfRestClient(api_key=VALID_API_KEY, transport=transport)
    report_pdf = get_test_resource_path("report.pdf")
    report_docx = get_test_resource_path("report.docx")
    try:
        response = client.files.create_from_paths([report_pdf, report_docx])
    finally:
        client.close()

    assert isinstance(response, list)
    assert len(response) == 2
    for file_repr in response:
        payload = info_payloads[file_repr.id]
        _assert_file_matches_payload(file_repr, payload)


def test_files_create_from_paths_single_path() -> None:
    uploaded_file_id = str(uuid.uuid4())
    info_payload = _build_file_info_payload(uploaded_file_id, "report.pdf")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/upload":
            body = request.content
            assert body.count(b'name="file"') == 1
            assert b'filename="report.pdf"' in body
            return httpx.Response(
                200,
                json={
                    "files": [
                        {"name": "report.pdf", "id": uploaded_file_id},
                    ]
                },
            )
        if request.method == "GET" and request.url.path.startswith("/resource/"):
            assert request.url.params["format"] == "info"
            return httpx.Response(200, json=info_payload)
        msg = f"Unexpected request: {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    client = PdfRestClient(api_key=VALID_API_KEY, transport=transport)
    report_pdf = get_test_resource_path("report.pdf")
    try:
        response = client.files.create_from_paths(report_pdf)
    finally:
        client.close()

    assert len(response) == 1
    _assert_file_matches_payload(response[0], info_payload)


def test_files_create_from_paths_supports_metadata() -> None:
    uploaded_file_id = str(uuid.uuid4())
    info_payload = _build_file_info_payload(uploaded_file_id, "report.pdf")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/upload":
            body = request.content
            assert b'filename="report.pdf"' in body
            assert b"Content-Type: application/test-pdf" in body
            assert b"X-Custom: header" in body
            return httpx.Response(
                200,
                json={
                    "files": [
                        {"name": "report.pdf", "id": uploaded_file_id},
                    ]
                },
            )
        if request.method == "GET":
            assert request.url.params["format"] == "info"
            return httpx.Response(200, json=info_payload)
        msg = f"Unexpected request: {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    client = PdfRestClient(api_key=VALID_API_KEY, transport=transport)
    report_pdf = get_test_resource_path("report.pdf")
    try:
        response = client.files.create_from_paths(
            [
                (
                    report_pdf,
                    "application/test-pdf",
                    {"X-Custom": "header"},
                )
            ]
        )
    finally:
        client.close()

    assert len(response) == 1
    _assert_file_matches_payload(response[0], info_payload)


def test_files_create_rejects_empty_input() -> None:
    client = PdfRestClient(
        api_key=VALID_API_KEY,
        transport=httpx.MockTransport(lambda _: httpx.Response(200)),
    )
    try:
        with pytest.raises(
            TypeError,
            match=r"Upload files must be provided as a sequence or a single file specification\.",
        ):
            client.files.create(cast(Any, {}))
        with pytest.raises(ValueError, match=r"At least one file must be provided\."):
            client.files.create([])
        with pytest.raises(
            ValueError, match=r"At least one file path must be provided\."
        ):
            client.files.create_from_paths([])
    finally:
        client.close()


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
            response = await client.files.create(
                [
                    ("report.pdf", pdf_file),
                    ("report.docx", docx_file),
                ]
            )

    assert isinstance(response, list)
    assert len(response) == 2
    for file_repr in response:
        payload = info_payloads[file_repr.id]
        _assert_file_matches_payload(file_repr, payload)


@pytest.mark.asyncio
async def test_async_files_create_from_paths() -> None:
    uploaded_ids = [str(uuid.uuid4()), str(uuid.uuid4())]
    info_payloads = {
        uploaded_ids[0]: _build_file_info_payload(uploaded_ids[0], "report.pdf"),
        uploaded_ids[1]: _build_file_info_payload(uploaded_ids[1], "report.docx"),
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/upload":
            body = request.content
            assert body.count(b'name="file"') == 2
            assert b'filename="report.pdf"' in body
            assert b'filename="report.docx"' in body
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
        response = await client.files.create_from_paths([report_pdf, report_docx])

    assert isinstance(response, list)
    assert len(response) == 2
    for file_repr in response:
        payload = info_payloads[file_repr.id]
        _assert_file_matches_payload(file_repr, payload)


@pytest.mark.asyncio
async def test_async_files_create_from_paths_single_path() -> None:
    uploaded_file_id = str(uuid.uuid4())
    info_payload = _build_file_info_payload(uploaded_file_id, "report.pdf")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/upload":
            body = request.content
            assert body.count(b'name="file"') == 1
            assert b'filename="report.pdf"' in body
            return httpx.Response(
                200,
                json={
                    "files": [
                        {"name": "report.pdf", "id": uploaded_file_id},
                    ]
                },
            )
        if request.method == "GET" and request.url.path.startswith("/resource/"):
            assert request.url.params["format"] == "info"
            return httpx.Response(200, json=info_payload)
        msg = f"Unexpected request: {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    client = AsyncPdfRestClient(api_key=VALID_API_KEY, transport=transport)
    report_pdf = get_test_resource_path("report.pdf")
    async with client:
        response = await client.files.create_from_paths(report_pdf)

    assert len(response) == 1
    _assert_file_matches_payload(response[0], info_payload)


def test_live_file_create(pdfrest_api_key: str, pdfrest_live_base_url: str) -> None:
    with PdfRestClient(
        api_key=pdfrest_api_key, base_url=pdfrest_live_base_url
    ) as client:
        report_pdf = get_test_resource_path("report.pdf")
        with report_pdf.open("rb") as pdf_file:
            response = client.files.create([pdf_file])
            assert isinstance(response, list)
            assert len(response) == 1
            file_repr = response[0]
            assert isinstance(file_repr, PdfRestFile)
            assert file_repr.id
            assert file_repr.name


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
            names = {file_repr.name for file_repr in response}
            assert {"report.pdf", "report.docx"} <= names


def test_live_file_create_from_paths(
    pdfrest_api_key: str, pdfrest_live_base_url: str
) -> None:
    with PdfRestClient(
        api_key=pdfrest_api_key, base_url=pdfrest_live_base_url
    ) as client:
        report_pdf = get_test_resource_path("report.pdf")
        report_docx = get_test_resource_path("report.docx")
        response = client.files.create_from_paths([report_pdf, report_docx])
        assert isinstance(response, list)
        assert len(response) == 2
        names = {file_repr.name for file_repr in response}
        assert {"report.pdf", "report.docx"} <= names


@pytest.mark.asyncio
async def test_live_async_file_create(
    pdfrest_api_key: str, pdfrest_live_base_url: str
) -> None:
    client = AsyncPdfRestClient(api_key=pdfrest_api_key, base_url=pdfrest_live_base_url)
    report_pdf = get_test_resource_path("report.pdf")
    async with client:
        with report_pdf.open("rb") as pdf_file:
            response = await client.files.create([pdf_file])
    assert isinstance(response, list)
    assert len(response) == 1
    file_repr = response[0]
    assert isinstance(file_repr, PdfRestFile)
    assert file_repr.id
    assert file_repr.name


@pytest.mark.asyncio
async def test_live_async_file_create_from_paths(
    pdfrest_api_key: str, pdfrest_live_base_url: str
) -> None:
    client = AsyncPdfRestClient(api_key=pdfrest_api_key, base_url=pdfrest_live_base_url)
    report_pdf = get_test_resource_path("report.pdf")
    report_docx = get_test_resource_path("report.docx")
    async with client:
        response = await client.files.create_from_paths([report_pdf, report_docx])
    assert isinstance(response, list)
    assert len(response) == 2
    names = {file_repr.name for file_repr in response}
    assert {"report.pdf", "report.docx"} <= names
