from __future__ import annotations

import uuid
from contextlib import AsyncExitStack, ExitStack
from dataclasses import dataclass
from pathlib import Path

import pytest

from pdfrest import AsyncPdfRestClient, PdfRestClient
from pdfrest.models import PdfRestFile


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
