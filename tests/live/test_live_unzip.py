from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from pdfrest import AsyncPdfRestClient, PdfRestApiError, PdfRestClient
from pdfrest.models import PdfRestFile

from ..resources import get_test_resource_path


def _build_zip_payload(tmp_path: Path) -> Path:
    zip_path = tmp_path / "sample.zip"
    with zipfile.ZipFile(zip_path, "w") as bundle:
        report_path = get_test_resource_path("report.pdf")
        bundle.write(report_path, arcname="report.pdf")
    return zip_path


@pytest.fixture(scope="module")
def uploaded_zip_file(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    tmp_path_factory: pytest.TempPathFactory,
) -> PdfRestFile:
    zip_path = _build_zip_payload(tmp_path_factory.mktemp("zip-input"))
    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        return client.files.create_from_paths([zip_path])[0]


def test_live_unzip_file(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_zip_file: PdfRestFile,
) -> None:
    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        response = client.unzip_file(uploaded_zip_file)

        assert response.output_files
        assert all(file.size > 0 for file in response.output_files)
        assert all(file.name for file in response.output_files)
        assert str(response.input_id) == str(uploaded_zip_file.id)


def test_live_unzip_invalid_override(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_zip_file: PdfRestFile,
) -> None:
    with (
        PdfRestClient(
            api_key=pdfrest_api_key,
            base_url=pdfrest_live_base_url,
        ) as client,
        pytest.raises(PdfRestApiError, match="id"),
    ):
        client.unzip_file(
            uploaded_zip_file,
            extra_body={"id": "not-a-uuid"},
        )


@pytest.mark.asyncio
async def test_live_unzip_file_async(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_zip_file: PdfRestFile,
) -> None:
    async with AsyncPdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        response = await client.unzip_file(
            uploaded_zip_file,
            extra_query={"trace": "async"},
        )

        assert response.output_files
        assert all(file.size > 0 for file in response.output_files)
        assert all(file.name for file in response.output_files)
        assert str(response.input_id) == str(uploaded_zip_file.id)
