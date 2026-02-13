from __future__ import annotations

import pytest

from pdfrest import AsyncPdfRestClient, PdfRestApiError, PdfRestClient
from pdfrest.models import PdfRestFile

from ..resources import get_test_resource_path

IMAGE_RESOURCE_VARIANTS = (
    pytest.param(("test.jpg", "image/jpeg"), id="jpeg"),
    pytest.param(("test.png", "image/png"), id="png"),
    pytest.param(("test.tif", "image/tiff"), id="tiff"),
    pytest.param(("test.gif", "image/gif"), id="gif"),
)


@pytest.fixture(scope="module")
def uploaded_pdf_for_image_addition(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
) -> PdfRestFile:
    resource = get_test_resource_path("report.pdf")
    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        return client.files.create_from_paths([resource])[0]


@pytest.fixture(scope="module", params=IMAGE_RESOURCE_VARIANTS)
def uploaded_image_variant(
    request: pytest.FixtureRequest,
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
) -> PdfRestFile:
    resource_name, expected_mime = request.param
    resource = get_test_resource_path(resource_name)
    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        uploaded_image = client.files.create_from_paths([resource])[0]

    assert uploaded_image.type == expected_mime
    return uploaded_image


def test_live_add_image_to_pdf(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf_for_image_addition: PdfRestFile,
    uploaded_image_variant: PdfRestFile,
) -> None:
    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        response = client.add_image_to_pdf(
            uploaded_pdf_for_image_addition,
            image=uploaded_image_variant,
            x=25,
            y=50,
            page=1,
            output="live-added-image",
        )

    assert response.output_files
    output_file = response.output_file
    assert output_file.type == "application/pdf"
    assert output_file.name.startswith("live-added-image")
    assert output_file.size > 0
    assert response.warning is None
    assert uploaded_pdf_for_image_addition.id in response.input_ids
    assert uploaded_image_variant.id in response.input_ids


@pytest.mark.asyncio
async def test_live_async_add_image_to_pdf(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf_for_image_addition: PdfRestFile,
    uploaded_image_variant: PdfRestFile,
) -> None:
    async with AsyncPdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        response = await client.add_image_to_pdf(
            uploaded_pdf_for_image_addition,
            image=uploaded_image_variant,
            x=75,
            y=125,
            page=1,
        )

    assert response.output_files
    output_file = response.output_file
    assert output_file.type == "application/pdf"
    assert output_file.size > 0
    assert response.warning is None
    assert uploaded_pdf_for_image_addition.id in response.input_ids
    assert uploaded_image_variant.id in response.input_ids


def test_live_add_image_to_pdf_invalid_page(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf_for_image_addition: PdfRestFile,
    uploaded_image_variant: PdfRestFile,
) -> None:
    with (
        PdfRestClient(
            api_key=pdfrest_api_key,
            base_url=pdfrest_live_base_url,
        ) as client,
        pytest.raises(PdfRestApiError, match=r"(?i)page"),
    ):
        client.add_image_to_pdf(
            uploaded_pdf_for_image_addition,
            image=uploaded_image_variant,
            x=0,
            y=0,
            page=1,
            extra_body={"page": 0},
        )


@pytest.mark.asyncio
async def test_live_async_add_image_to_pdf_invalid_page(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf_for_image_addition: PdfRestFile,
    uploaded_image_variant: PdfRestFile,
) -> None:
    async with AsyncPdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        with pytest.raises(PdfRestApiError, match=r"(?i)page"):
            await client.add_image_to_pdf(
                uploaded_pdf_for_image_addition,
                image=uploaded_image_variant,
                x=0,
                y=0,
                page=1,
                extra_body={"page": 0},
            )
