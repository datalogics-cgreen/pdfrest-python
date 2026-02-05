from __future__ import annotations

import pytest

from pdfrest import AsyncPdfRestClient, PdfRestClient
from pdfrest.models import PdfRestFileBasedResponse

from ..resources import get_test_resource_path


def test_live_convert_to_png(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
) -> None:
    resource = get_test_resource_path("report.pdf")
    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        uploaded = client.files.create_from_paths([resource])[0]
        response = client.convert_to_png(
            uploaded,
            output_prefix="live-convert",
            page_range="1",
        )

    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.output_files


@pytest.mark.asyncio
async def test_live_async_convert_to_png(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
) -> None:
    resource = get_test_resource_path("report.pdf")
    async with AsyncPdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        uploaded = (await client.files.create_from_paths([resource]))[0]
        response = await client.convert_to_png(
            uploaded,
            output_prefix="live-async-convert",
            page_range="1",
        )

    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.output_files
