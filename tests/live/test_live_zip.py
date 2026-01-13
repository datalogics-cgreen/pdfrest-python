from __future__ import annotations

import pytest

from pdfrest import AsyncPdfRestClient, PdfRestApiError, PdfRestClient
from pdfrest.models import PdfRestFile

from ..resources import get_test_resource_path


@pytest.fixture(scope="module")
def uploaded_zip_inputs(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
) -> list[PdfRestFile]:
    paths = [
        get_test_resource_path("report.pdf"),
        get_test_resource_path("report.docx"),
    ]
    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        return client.files.create_from_paths(paths)


def test_live_zip_files(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_zip_inputs: list[PdfRestFile],
) -> None:
    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        response = client.zip_files(
            uploaded_zip_inputs,
            output="live-zip",
        )

        assert response.output_file.name.startswith("live-zip")
        assert response.output_file.name.endswith(".zip")
        assert response.output_file.type == "application/zip"
        assert response.output_file.size > 0
        assert {str(file.id) for file in uploaded_zip_inputs} == {
            str(file_id) for file_id in response.input_ids
        }


def test_live_zip_files_invalid_id_override(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_zip_inputs: list[PdfRestFile],
) -> None:
    with (
        PdfRestClient(
            api_key=pdfrest_api_key,
            base_url=pdfrest_live_base_url,
        ) as client,
        pytest.raises(PdfRestApiError, match="id"),
    ):
        client.zip_files(
            uploaded_zip_inputs,
            extra_body={"id": "not-a-uuid"},
        )


@pytest.mark.asyncio
async def test_live_zip_files_async(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_zip_inputs: list[PdfRestFile],
) -> None:
    async with AsyncPdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        response = await client.zip_files(
            uploaded_zip_inputs,
            output="live-zip-async",
            extra_query={"trace": "async"},
        )

        assert response.output_file.name.startswith("live-zip-async")
        assert response.output_file.name.endswith(".zip")
        assert response.output_file.type == "application/zip"
        assert response.output_file.size > 0
        assert {str(file.id) for file in uploaded_zip_inputs} == {
            str(file_id) for file_id in response.input_ids
        }
