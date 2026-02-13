from __future__ import annotations

import pytest

from pdfrest import AsyncPdfRestClient, PdfRestClient
from pdfrest.models import PdfRestFile

from ..resources import get_test_resource_path


@pytest.fixture(scope="module")
def uploaded_html_for_pdf(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
) -> PdfRestFile:
    resource = get_test_resource_path("sample.html")
    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        return client.files.create_from_paths([resource])[0]


def test_live_convert_html_to_pdf_success(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_html_for_pdf: PdfRestFile,
) -> None:
    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        response = client.convert_html_to_pdf(
            uploaded_html_for_pdf,
            output="live-html-file",
            page_size="letter",
            page_margin="8mm",
            page_orientation="portrait",
            web_layout="desktop",
        )

    assert response.output_files
    output_file = response.output_file
    assert output_file.type == "application/pdf"
    assert output_file.size > 0
    assert response.warning is None
    assert str(response.input_id) == str(uploaded_html_for_pdf.id)
    assert output_file.name.startswith("live-html-file")


@pytest.mark.asyncio
async def test_live_async_convert_html_to_pdf_success(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_html_for_pdf: PdfRestFile,
) -> None:
    async with AsyncPdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        response = await client.convert_html_to_pdf(
            uploaded_html_for_pdf,
            output="live-html-file-async",
            page_orientation="landscape",
        )

    assert response.output_files
    output_file = response.output_file
    assert output_file.type == "application/pdf"
    assert output_file.size > 0
    assert response.warning is None
    assert str(response.input_id) == str(uploaded_html_for_pdf.id)
    assert output_file.name.startswith("live-html-file-async")
