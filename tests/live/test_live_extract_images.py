from __future__ import annotations

import pytest

from pdfrest import AsyncPdfRestClient, PdfRestApiError, PdfRestClient
from pdfrest.models import PdfRestFileBasedResponse

from ..resources import get_test_resource_path


def test_live_extract_images_success(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
) -> None:
    resource = get_test_resource_path("duckhat.pdf")
    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        uploaded = client.files.create_from_paths([resource])[0]
        response = client.extract_images(uploaded)

    assert isinstance(response, PdfRestFileBasedResponse)
    output_files = response.output_files
    assert output_files
    assert all(file.name for file in output_files)
    assert all(
        file.type and (file.type.startswith("image/") or file.type == "application/zip")
        for file in output_files
    )
    assert all(file.size > 0 for file in output_files)
    assert response.warning is None
    assert response.input_id == uploaded.id


@pytest.mark.asyncio
async def test_live_async_extract_images_success(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
) -> None:
    resource = get_test_resource_path("duckhat.pdf")
    async with AsyncPdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        uploaded = (await client.files.create_from_paths([resource]))[0]
        response = await client.extract_images(uploaded, output="async-images")

    assert isinstance(response, PdfRestFileBasedResponse)
    output_files = response.output_files
    assert output_files
    assert output_files[0].name.startswith("async-images")
    assert all(file.name for file in output_files)
    assert all(
        file.type and (file.type.startswith("image/") or file.type == "application/zip")
        for file in output_files
    )
    assert all(file.size > 0 for file in output_files)
    assert response.warning is None
    assert response.input_id == uploaded.id


def test_live_extract_images_invalid_pages(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
) -> None:
    resource = get_test_resource_path("duckhat.pdf")
    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        uploaded = client.files.create_from_paths([resource])[0]
        with pytest.raises(PdfRestApiError, match=r"(?i)page"):
            client.extract_images(
                uploaded,
                extra_body={"pages": "last-1"},
            )


@pytest.mark.asyncio
async def test_live_async_extract_images_invalid_pages(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
) -> None:
    resource = get_test_resource_path("duckhat.pdf")
    async with AsyncPdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        uploaded = (await client.files.create_from_paths([resource]))[0]
        with pytest.raises(PdfRestApiError, match=r"(?i)page"):
            await client.extract_images(
                uploaded,
                extra_body={"pages": "last-1"},
            )
