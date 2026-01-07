from __future__ import annotations

import pytest

from pdfrest import AsyncPdfRestClient, PdfRestApiError, PdfRestClient
from pdfrest.models import PdfRestFileBasedResponse

from ..resources import get_test_resource_path


def test_live_convert_to_markdown_success(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
) -> None:
    resource = get_test_resource_path("report.pdf")
    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        uploaded = client.files.create_from_paths([resource])[0]
        response = client.convert_to_markdown(uploaded)

    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.output_files
    output_file = response.output_file
    assert output_file.name.endswith(".md")
    assert output_file.type == "text/markdown"
    assert output_file.size > 0
    assert response.warning is None
    assert response.input_id == uploaded.id


@pytest.mark.asyncio
async def test_live_async_convert_to_markdown_success(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
) -> None:
    resource = get_test_resource_path("report.pdf")
    async with AsyncPdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        uploaded = (await client.files.create_from_paths([resource]))[0]
        response = await client.convert_to_markdown(uploaded, output="async-md")

    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.output_files
    output_file = response.output_file
    assert output_file.name.startswith("async-md")
    assert output_file.type == "text/markdown"
    assert output_file.size > 0
    assert response.warning is None
    assert response.input_id == uploaded.id


def test_live_convert_to_markdown_invalid_pages(
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
            client.convert_to_markdown(
                uploaded,
                extra_body={"pages": "last-1"},
            )


@pytest.mark.asyncio
async def test_live_async_convert_to_markdown_invalid_pages(
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
            await client.convert_to_markdown(
                uploaded,
                extra_body={"pages": "last-1"},
            )
