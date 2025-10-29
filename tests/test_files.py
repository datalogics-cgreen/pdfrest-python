from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator, Iterator
from contextlib import AsyncExitStack, ExitStack
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

import httpx
import pytest
import pytest_asyncio

from pdfrest import AsyncPdfRestClient, PdfRestClient
from pdfrest.models import PdfRestFile

from .resources import get_test_resource_path

VALID_API_KEY = "12345678-1234-1234-1234-123456789abc"


class _StaticStream(httpx.SyncByteStream):
    def __init__(self, payload: bytes) -> None:
        self._payload = payload
        self._consumed = False

    def __iter__(self) -> Iterator[bytes]:
        if self._consumed:
            return iter(())
        self._consumed = True
        return iter((self._payload,))

    def close(self) -> None:  # pragma: no cover - trivial
        ...


class _StaticAsyncStream(httpx.AsyncByteStream):
    def __init__(self, payload: bytes) -> None:
        self._payload = payload
        self._consumed = False

    async def __aiter__(self):
        if not self._consumed:
            self._consumed = True
            yield self._payload

    async def aclose(self) -> None:  # pragma: no cover - trivial
        ...


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


def _create_temp_text_file(tmp_path: Path, prefix: str) -> tuple[Path, str, bytes]:
    filename = f"{prefix}.txt"
    source_path = tmp_path / filename
    source_content = f"{prefix}-line1\n{prefix}-line2\n"
    source_path.write_text(source_content, encoding="utf-8")
    return source_path, source_content, source_path.read_bytes()


@dataclass
class LiveFileData:
    prefix: str
    file: PdfRestFile
    original_bytes: bytes
    source_text: str


@pytest.fixture(scope="class")
def live_sync_file(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    tmp_path_factory: pytest.TempPathFactory,
) -> LiveFileData:
    prefix = f"sync-live-{uuid.uuid4().hex}"
    temp_dir = tmp_path_factory.mktemp(prefix)
    source_path, source_text, source_bytes = _create_temp_text_file(temp_dir, prefix)
    with PdfRestClient(
        api_key=pdfrest_api_key, base_url=pdfrest_live_base_url
    ) as client:
        with source_path.open("rb") as source_file:
            uploaded_files = client.files.create([source_file])
        file_repr = uploaded_files[0]
    return LiveFileData(
        prefix=prefix,
        file=file_repr,
        original_bytes=source_bytes,
        source_text=source_text,
    )


@pytest.fixture(scope="class")
def live_async_file(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    tmp_path_factory: pytest.TempPathFactory,
) -> LiveFileData:
    prefix = f"async-live-{uuid.uuid4().hex}"
    temp_dir = tmp_path_factory.mktemp(prefix)
    source_path, source_text, source_bytes = _create_temp_text_file(temp_dir, prefix)
    with PdfRestClient(
        api_key=pdfrest_api_key, base_url=pdfrest_live_base_url
    ) as client:
        with source_path.open("rb") as source_file:
            uploaded_files = client.files.create([source_file])
        file_repr = uploaded_files[0]
    return LiveFileData(
        prefix=prefix,
        file=file_repr,
        original_bytes=source_bytes,
        source_text=source_text,
    )


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
    report_pdf = get_test_resource_path("report.pdf")
    with (
        PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client,
        report_pdf.open("rb") as pdf_file,
    ):
        response = client.files.create([("report.pdf", pdf_file)])

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
    report_pdf = get_test_resource_path("report.pdf")
    report_docx = get_test_resource_path("report.docx")
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.files.create_from_paths([report_pdf, report_docx])

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
    report_pdf = get_test_resource_path("report.pdf")
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.files.create_from_paths(report_pdf)

    assert len(response) == 1
    _assert_file_matches_payload(response[0], info_payload)


def test_files_create_from_urls_uses_upload_and_info() -> None:
    uploaded_ids = [str(uuid.uuid4()), str(uuid.uuid4())]
    info_payloads = {
        uploaded_ids[0]: _build_file_info_payload(uploaded_ids[0], "report.pdf"),
        uploaded_ids[1]: _build_file_info_payload(uploaded_ids[1], "report.docx"),
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/upload":
            payload = json.loads(request.content.decode("utf-8"))
            assert payload["url"] == [
                "https://example.com/report.pdf",
                "https://example.com/report.docx",
            ]
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
            return httpx.Response(200, json=info_payloads[file_id])
        msg = f"Unexpected request: {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.files.create_from_urls(
            [
                "https://example.com/report.pdf",
                httpx.URL("https://example.com/report.docx"),
            ]
        )

    assert len(response) == 2
    for file_repr in response:
        payload = info_payloads[file_repr.id]
        _assert_file_matches_payload(file_repr, payload)


def test_files_create_from_urls_single_url() -> None:
    uploaded_file_id = str(uuid.uuid4())
    info_payload = _build_file_info_payload(uploaded_file_id, "report.pdf")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/upload":
            payload = json.loads(request.content.decode("utf-8"))
            assert payload["url"] == ["https://example.com/report.pdf"]
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
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.files.create_from_urls("https://example.com/report.pdf")

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
    report_pdf = get_test_resource_path("report.pdf")
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.files.create_from_paths(
            [
                (
                    report_pdf,
                    "application/test-pdf",
                    {"X-Custom": "header"},
                )
            ]
        )

    assert len(response) == 1
    _assert_file_matches_payload(response[0], info_payload)


class TestDownloadHelpers:
    @pytest.fixture
    def client(self) -> Iterator[tuple[PdfRestClient, bytes, dict[str, Any]]]:
        binary_content = b"line1\nline2\n"
        json_payload: dict[str, Any] = {"message": "hi"}

        def handler(request: httpx.Request) -> httpx.Response:
            if request.method == "GET" and request.url.path == "/resource/file-id":
                return httpx.Response(200, stream=_StaticStream(binary_content))
            if request.method == "GET" and request.url.path == "/resource/file-id-json":
                payload = json.dumps(json_payload).encode("utf-8")
                return httpx.Response(200, stream=_StaticStream(payload))
            msg = f"Unexpected request: {request.method} {request.url}"
            raise AssertionError(msg)

        transport = httpx.MockTransport(handler)
        with PdfRestClient(
            api_key=VALID_API_KEY, transport=transport
        ) as pdfrest_client:
            yield pdfrest_client, binary_content, json_payload

    def test_read_bytes(
        self, client: tuple[PdfRestClient, bytes, dict[str, Any]]
    ) -> None:
        pdfrest_client, binary_content, _ = client
        assert pdfrest_client.files.read_bytes("file-id") == binary_content

    def test_read_text(
        self, client: tuple[PdfRestClient, bytes, dict[str, Any]]
    ) -> None:
        pdfrest_client, binary_content, _ = client
        assert pdfrest_client.files.read_text("file-id") == binary_content.decode()

    def test_read_json(
        self, client: tuple[PdfRestClient, bytes, dict[str, Any]]
    ) -> None:
        pdfrest_client, _, json_payload = client
        assert pdfrest_client.files.read_json("file-id-json") == json_payload

    def test_write_bytes(
        self,
        client: tuple[PdfRestClient, bytes, dict[str, Any]],
        tmp_path: Path,
    ) -> None:
        pdfrest_client, binary_content, _ = client
        destination = tmp_path / "download.bin"
        written_path = pdfrest_client.files.write_bytes("file-id", destination)
        assert written_path.read_bytes() == binary_content

    def test_stream_iter_raw(
        self, client: tuple[PdfRestClient, bytes, dict[str, Any]]
    ) -> None:
        pdfrest_client, binary_content, _ = client
        with pdfrest_client.files.stream("file-id") as stream:
            raw_chunks = list(stream.iter_raw())
        assert b"".join(raw_chunks) == binary_content

    def test_stream_iter_bytes(
        self, client: tuple[PdfRestClient, bytes, dict[str, Any]]
    ) -> None:
        pdfrest_client, binary_content, _ = client
        with pdfrest_client.files.stream("file-id") as stream:
            chunks = list(stream.iter_bytes())
        assert b"".join(chunks) == binary_content

    def test_stream_iter_text(
        self, client: tuple[PdfRestClient, bytes, dict[str, Any]]
    ) -> None:
        pdfrest_client, binary_content, _ = client
        with pdfrest_client.files.stream("file-id") as stream:
            text_chunks = list(stream.iter_text())
        assert "".join(text_chunks) == binary_content.decode()

    def test_stream_iter_lines(
        self, client: tuple[PdfRestClient, bytes, dict[str, Any]]
    ) -> None:
        pdfrest_client, binary_content, _ = client
        with pdfrest_client.files.stream("file-id") as stream:
            lines = list(stream.iter_lines())
        assert lines == binary_content.decode().splitlines()


@pytest.mark.asyncio
class TestAsyncDownloadHelpers:
    @pytest_asyncio.fixture
    async def client(
        self,
    ) -> AsyncIterator[tuple[AsyncPdfRestClient, bytes, dict[str, Any]]]:
        binary_content = b"line1\nline2\n"
        json_payload: dict[str, Any] = {"message": "hi"}

        def handler(request: httpx.Request) -> httpx.Response:
            if request.method == "GET" and request.url.path == "/resource/file-id":
                return httpx.Response(200, stream=_StaticAsyncStream(binary_content))
            if request.method == "GET" and request.url.path == "/resource/file-id-json":
                payload = json.dumps(json_payload).encode("utf-8")
                return httpx.Response(200, stream=_StaticAsyncStream(payload))
            msg = f"Unexpected request: {request.method} {request.url}"
            raise AssertionError(msg)

        transport = httpx.MockTransport(handler)
        async with AsyncPdfRestClient(
            api_key=VALID_API_KEY, transport=transport
        ) as pdfrest_client:
            yield pdfrest_client, binary_content, json_payload

    async def test_read_bytes(
        self, client: tuple[AsyncPdfRestClient, bytes, dict[str, Any]]
    ) -> None:
        pdfrest_client, binary_content, _ = client
        assert await pdfrest_client.files.read_bytes("file-id") == binary_content

    async def test_read_text(
        self, client: tuple[AsyncPdfRestClient, bytes, dict[str, Any]]
    ) -> None:
        pdfrest_client, binary_content, _ = client
        assert (
            await pdfrest_client.files.read_text("file-id") == binary_content.decode()
        )

    async def test_read_json(
        self, client: tuple[AsyncPdfRestClient, bytes, dict[str, Any]]
    ) -> None:
        pdfrest_client, _, json_payload = client
        assert await pdfrest_client.files.read_json("file-id-json") == json_payload

    async def test_write_bytes(
        self,
        client: tuple[AsyncPdfRestClient, bytes, dict[str, Any]],
        tmp_path: Path,
    ) -> None:
        pdfrest_client, binary_content, _ = client
        destination = tmp_path / "async-download.bin"
        written_path = await pdfrest_client.files.write_bytes("file-id", destination)
        assert written_path.read_bytes() == binary_content

    async def test_stream_iter_raw(
        self, client: tuple[AsyncPdfRestClient, bytes, dict[str, Any]]
    ) -> None:
        pdfrest_client, binary_content, _ = client
        async with await pdfrest_client.files.stream("file-id") as stream:
            raw_chunks = [chunk async for chunk in stream.iter_raw()]
        assert b"".join(raw_chunks) == binary_content

    async def test_stream_iter_bytes(
        self, client: tuple[AsyncPdfRestClient, bytes, dict[str, Any]]
    ) -> None:
        pdfrest_client, binary_content, _ = client
        async with await pdfrest_client.files.stream("file-id") as stream:
            chunks = [chunk async for chunk in stream.iter_bytes()]
        assert b"".join(chunks) == binary_content

    async def test_stream_iter_text(
        self, client: tuple[AsyncPdfRestClient, bytes, dict[str, Any]]
    ) -> None:
        pdfrest_client, binary_content, _ = client
        async with await pdfrest_client.files.stream("file-id") as stream:
            text_chunks = [chunk async for chunk in stream.iter_text()]
        assert "".join(text_chunks) == binary_content.decode()

    async def test_stream_iter_lines(
        self, client: tuple[AsyncPdfRestClient, bytes, dict[str, Any]]
    ) -> None:
        pdfrest_client, binary_content, _ = client
        async with await pdfrest_client.files.stream("file-id") as stream:
            lines = [line async for line in stream.iter_lines()]
        assert lines == binary_content.decode().splitlines()


@pytest.mark.asyncio
async def test_async_files_create_from_urls_invalid_scheme() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(400))
    async with AsyncPdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        with pytest.raises(
            ValueError, match=r"URL uploads require http or https scheme\."
        ):
            await client.files.create_from_urls("ftp://example.com/file.pdf")


def test_files_create_rejects_empty_input() -> None:
    with PdfRestClient(
        api_key=VALID_API_KEY,
        transport=httpx.MockTransport(lambda _: httpx.Response(200)),
    ) as client:
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
        with pytest.raises(ValueError, match=r"At least one URL must be provided\."):
            client.files.create_from_urls([])


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

    report_pdf = get_test_resource_path("report.pdf")
    report_docx = get_test_resource_path("report.docx")
    async with AsyncPdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
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
async def test_async_files_create_from_urls() -> None:
    uploaded_ids = [str(uuid.uuid4()), str(uuid.uuid4())]
    info_payloads = {
        uploaded_ids[0]: _build_file_info_payload(uploaded_ids[0], "report.pdf"),
        uploaded_ids[1]: _build_file_info_payload(uploaded_ids[1], "report.docx"),
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/upload":
            payload = json.loads(request.content.decode("utf-8"))
            assert payload["url"] == [
                "https://example.com/report.pdf",
                "https://example.com/report.docx",
            ]
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
            return httpx.Response(200, json=info_payloads[file_id])
        msg = f"Unexpected request: {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    async with AsyncPdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = await client.files.create_from_urls(
            [
                "https://example.com/report.pdf",
                httpx.URL("https://example.com/report.docx"),
            ]
        )

    assert len(response) == 2
    for file_repr in response:
        payload = info_payloads[file_repr.id]
        _assert_file_matches_payload(file_repr, payload)


@pytest.mark.asyncio
async def test_async_files_create_from_urls_single_url() -> None:
    uploaded_file_id = str(uuid.uuid4())
    info_payload = _build_file_info_payload(uploaded_file_id, "report.pdf")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/upload":
            payload = json.loads(request.content.decode("utf-8"))
            assert payload["url"] == ["https://example.com/report.pdf"]
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
    async with AsyncPdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = await client.files.create_from_urls("https://example.com/report.pdf")

    assert len(response) == 1
    _assert_file_matches_payload(response[0], info_payload)


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
    report_pdf = get_test_resource_path("report.pdf")
    report_docx = get_test_resource_path("report.docx")
    async with AsyncPdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
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
    report_pdf = get_test_resource_path("report.pdf")
    async with AsyncPdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
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
        assert {
            "report.pdf",
            "report.docx",
        } <= names


def test_live_file_create_from_urls(
    pdfrest_api_key: str, pdfrest_live_base_url: str
) -> None:
    with PdfRestClient(
        api_key=pdfrest_api_key, base_url=pdfrest_live_base_url
    ) as client:
        report_pdf = get_test_resource_path("report.pdf")
        report_docx = get_test_resource_path("report.docx")
        base_files = client.files.create_from_paths([report_pdf, report_docx])
        source_urls = [str(file_repr.url) for file_repr in base_files]
        response = client.files.create_from_urls(source_urls)
        assert isinstance(response, list)
        assert len(response) == 2
        names = {file_repr.name for file_repr in response}
        assert {"report.pdf", "report.docx"} <= names


class TestLiveFileDownloads:
    def test_read_bytes(
        self,
        pdfrest_api_key: str,
        pdfrest_live_base_url: str,
        live_sync_file: LiveFileData,
    ) -> None:
        with PdfRestClient(
            api_key=pdfrest_api_key, base_url=pdfrest_live_base_url
        ) as client:
            assert (
                client.files.read_bytes(live_sync_file.file.id)
                == live_sync_file.original_bytes
            )

    def test_read_text(
        self,
        pdfrest_api_key: str,
        pdfrest_live_base_url: str,
        live_sync_file: LiveFileData,
    ) -> None:
        with PdfRestClient(
            api_key=pdfrest_api_key, base_url=pdfrest_live_base_url
        ) as client:
            assert (
                client.files.read_text(live_sync_file.file.id)
                == live_sync_file.source_text
            )

    def test_write_bytes(
        self,
        pdfrest_api_key: str,
        pdfrest_live_base_url: str,
        tmp_path: Path,
        live_sync_file: LiveFileData,
    ) -> None:
        destination = tmp_path / f"{live_sync_file.prefix}-download.bin"
        with PdfRestClient(
            api_key=pdfrest_api_key, base_url=pdfrest_live_base_url
        ) as client:
            written_path = client.files.write_bytes(
                live_sync_file.file.id, str(destination)
            )
        assert written_path == destination
        assert written_path.read_bytes() == live_sync_file.original_bytes

    def test_stream_iter_raw(
        self,
        pdfrest_api_key: str,
        pdfrest_live_base_url: str,
        live_sync_file: LiveFileData,
    ) -> None:
        with ExitStack() as stack:
            client = stack.enter_context(
                PdfRestClient(api_key=pdfrest_api_key, base_url=pdfrest_live_base_url)
            )
            stream = stack.enter_context(client.files.stream(live_sync_file.file.id))
            raw_chunks = list(stream.iter_raw())
            assert b"".join(raw_chunks) == live_sync_file.original_bytes

    def test_stream_iter_bytes(
        self,
        pdfrest_api_key: str,
        pdfrest_live_base_url: str,
        live_sync_file: LiveFileData,
    ) -> None:
        with ExitStack() as stack:
            client = stack.enter_context(
                PdfRestClient(api_key=pdfrest_api_key, base_url=pdfrest_live_base_url)
            )
            stream = stack.enter_context(client.files.stream(live_sync_file.file.id))
            chunks = list(stream.iter_bytes(chunk_size=None))
            assert b"".join(chunks) == live_sync_file.original_bytes

    def test_stream_iter_text(
        self,
        pdfrest_api_key: str,
        pdfrest_live_base_url: str,
        live_sync_file: LiveFileData,
    ) -> None:
        with ExitStack() as stack:
            client = stack.enter_context(
                PdfRestClient(api_key=pdfrest_api_key, base_url=pdfrest_live_base_url)
            )
            stream = stack.enter_context(client.files.stream(live_sync_file.file.id))
            text_chunks = list(stream.iter_text(chunk_size=None))
            assert "".join(text_chunks) == live_sync_file.source_text

    def test_stream_iter_lines(
        self,
        pdfrest_api_key: str,
        pdfrest_live_base_url: str,
        live_sync_file: LiveFileData,
    ) -> None:
        with ExitStack() as stack:
            client = stack.enter_context(
                PdfRestClient(api_key=pdfrest_api_key, base_url=pdfrest_live_base_url)
            )
            stream = stack.enter_context(client.files.stream(live_sync_file.file.id))
            lines = list(stream.iter_lines())
            assert lines == live_sync_file.source_text.splitlines()


@pytest.mark.asyncio
async def test_live_async_file_create(
    pdfrest_api_key: str, pdfrest_live_base_url: str
) -> None:
    report_pdf = get_test_resource_path("report.pdf")
    async with AsyncPdfRestClient(
        api_key=pdfrest_api_key, base_url=pdfrest_live_base_url
    ) as client:
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
    report_pdf = get_test_resource_path("report.pdf")
    report_docx = get_test_resource_path("report.docx")
    async with AsyncPdfRestClient(
        api_key=pdfrest_api_key, base_url=pdfrest_live_base_url
    ) as client:
        response = await client.files.create_from_paths([report_pdf, report_docx])
    assert isinstance(response, list)
    assert len(response) == 2
    names = {file_repr.name for file_repr in response}
    assert {
        "report.pdf",
        "report.docx",
    } <= names


class TestLiveAsyncFileDownloads:
    @pytest.mark.asyncio
    async def test_read_bytes(
        self,
        pdfrest_api_key: str,
        pdfrest_live_base_url: str,
        live_async_file: LiveFileData,
    ) -> None:
        async with AsyncPdfRestClient(
            api_key=pdfrest_api_key, base_url=pdfrest_live_base_url
        ) as client:
            assert (
                await client.files.read_bytes(live_async_file.file.id)
                == live_async_file.original_bytes
            )

    @pytest.mark.asyncio
    async def test_read_text(
        self,
        pdfrest_api_key: str,
        pdfrest_live_base_url: str,
        live_async_file: LiveFileData,
    ) -> None:
        async with AsyncPdfRestClient(
            api_key=pdfrest_api_key, base_url=pdfrest_live_base_url
        ) as client:
            assert (
                await client.files.read_text(live_async_file.file.id)
                == live_async_file.source_text
            )

    @pytest.mark.asyncio
    async def test_write_bytes(
        self,
        pdfrest_api_key: str,
        pdfrest_live_base_url: str,
        tmp_path: Path,
        live_async_file: LiveFileData,
    ) -> None:
        destination = tmp_path / f"{live_async_file.prefix}-download.bin"
        async with AsyncPdfRestClient(
            api_key=pdfrest_api_key, base_url=pdfrest_live_base_url
        ) as client:
            written_path = await client.files.write_bytes(
                live_async_file.file, destination
            )
        assert written_path == destination
        assert written_path.read_bytes() == live_async_file.original_bytes

    @pytest.mark.asyncio
    async def test_stream_iter_raw(
        self,
        pdfrest_api_key: str,
        pdfrest_live_base_url: str,
        live_async_file: LiveFileData,
    ) -> None:
        async with AsyncExitStack() as stack:
            client = await stack.enter_async_context(
                AsyncPdfRestClient(
                    api_key=pdfrest_api_key, base_url=pdfrest_live_base_url
                )
            )
            stream_cm = await client.files.stream(live_async_file.file.id)
            stream = await stack.enter_async_context(stream_cm)
            raw_chunks = [chunk async for chunk in stream.iter_raw()]
            assert b"".join(raw_chunks) == live_async_file.original_bytes

    @pytest.mark.asyncio
    async def test_stream_iter_bytes(
        self,
        pdfrest_api_key: str,
        pdfrest_live_base_url: str,
        live_async_file: LiveFileData,
    ) -> None:
        async with AsyncExitStack() as stack:
            client = await stack.enter_async_context(
                AsyncPdfRestClient(
                    api_key=pdfrest_api_key, base_url=pdfrest_live_base_url
                )
            )
            stream_cm = await client.files.stream(live_async_file.file.id)
            stream = await stack.enter_async_context(stream_cm)
            chunks = [chunk async for chunk in stream.iter_bytes(chunk_size=None)]
            assert b"".join(chunks) == live_async_file.original_bytes

    @pytest.mark.asyncio
    async def test_stream_iter_text(
        self,
        pdfrest_api_key: str,
        pdfrest_live_base_url: str,
        live_async_file: LiveFileData,
    ) -> None:
        async with AsyncExitStack() as stack:
            client = await stack.enter_async_context(
                AsyncPdfRestClient(
                    api_key=pdfrest_api_key, base_url=pdfrest_live_base_url
                )
            )
            stream_cm = await client.files.stream(live_async_file.file.id)
            stream = await stack.enter_async_context(stream_cm)
            text_chunks = [chunk async for chunk in stream.iter_text(chunk_size=None)]
            assert "".join(text_chunks) == live_async_file.source_text

    @pytest.mark.asyncio
    async def test_stream_iter_lines(
        self,
        pdfrest_api_key: str,
        pdfrest_live_base_url: str,
        live_async_file: LiveFileData,
    ) -> None:
        async with AsyncExitStack() as stack:
            client = await stack.enter_async_context(
                AsyncPdfRestClient(
                    api_key=pdfrest_api_key, base_url=pdfrest_live_base_url
                )
            )
            stream_cm = await client.files.stream(live_async_file.file.id)
            stream = await stack.enter_async_context(stream_cm)
            lines = [line async for line in stream.iter_lines()]
            assert lines == live_async_file.source_text.splitlines()


@pytest.mark.asyncio
async def test_live_async_file_create_from_urls(
    pdfrest_api_key: str, pdfrest_live_base_url: str
) -> None:
    report_pdf = get_test_resource_path("report.pdf")
    report_docx = get_test_resource_path("report.docx")
    async with AsyncPdfRestClient(
        api_key=pdfrest_api_key, base_url=pdfrest_live_base_url
    ) as client:
        base_files = await client.files.create_from_paths([report_pdf, report_docx])
        source_urls = [str(file_repr.url) for file_repr in base_files]
        response = await client.files.create_from_urls(source_urls)
    assert isinstance(response, list)
    assert len(response) == 2
    names = {file_repr.name for file_repr in response}
    assert {"report.pdf", "report.docx"} <= names
