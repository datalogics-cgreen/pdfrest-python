from __future__ import annotations

import pytest

from pdfrest import AsyncPdfRestClient, PdfRestApiError, PdfRestClient

LIVE_HTML_URL = "https://example.com"


def test_live_convert_url_to_pdf_success(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
) -> None:
    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        response = client.convert_url_to_pdf(
            LIVE_HTML_URL,
            output="live-html-url",
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
    assert str(response.input_id)
    assert output_file.name.startswith("live-html-url")


@pytest.mark.asyncio
async def test_live_async_convert_url_to_pdf_invalid_page_size(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
) -> None:
    async with AsyncPdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        with pytest.raises(PdfRestApiError, match=r"(?i)page_size|page size"):
            await client.convert_url_to_pdf(
                LIVE_HTML_URL,
                extra_body={"page_size": "poster"},
            )
