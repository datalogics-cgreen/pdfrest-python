from __future__ import annotations

import pytest

from pdfrest import AsyncPdfRestClient, PdfRestApiError, PdfRestClient
from pdfrest.models import PdfRestFileBasedResponse

from ..resources import get_test_resource_path


def test_live_extract_pdf_text_to_file_success(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
) -> None:
    resource = get_test_resource_path("report.pdf")
    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        uploaded = client.files.create_from_paths([resource])[0]
        response = client.extract_pdf_text_to_file(
            uploaded,
            full_text="document",
            preserve_line_breaks="on",
            word_style="off",
            word_coordinates="off",
        )

    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.output_files
    output_file = response.output_file
    assert output_file.name.endswith(".txt")
    assert output_file.type == "text/plain"
    assert output_file.size > 0
    assert response.warning is None
    assert response.input_id == uploaded.id


@pytest.mark.asyncio
async def test_live_async_extract_pdf_text_to_file_success(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
) -> None:
    resource = get_test_resource_path("report.pdf")
    async with AsyncPdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        uploaded = (await client.files.create_from_paths([resource]))[0]
        response = await client.extract_pdf_text_to_file(
            uploaded,
            full_text="document",
            preserve_line_breaks="on",
            word_style="off",
            word_coordinates="off",
            output="async-text",
        )

    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.output_files
    output_file = response.output_file
    assert output_file.name.startswith("async-text")
    assert output_file.type == "text/plain"
    assert output_file.size > 0
    assert response.warning is None
    assert response.input_id == uploaded.id


def test_live_extract_pdf_text_to_file_invalid_pages(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
) -> None:
    resource = get_test_resource_path("report.pdf")
    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        uploaded = client.files.create_from_paths([resource])[0]
        with pytest.raises(PdfRestApiError):
            client.extract_pdf_text_to_file(
                uploaded,
                extra_body={"pages": "last-1"},
            )


@pytest.mark.asyncio
async def test_live_async_extract_pdf_text_to_file_invalid_pages(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
) -> None:
    resource = get_test_resource_path("report.pdf")
    async with AsyncPdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        uploaded = (await client.files.create_from_paths([resource]))[0]
        with pytest.raises(PdfRestApiError):
            await client.extract_pdf_text_to_file(
                uploaded,
                extra_body={"pages": "last-1"},
            )
