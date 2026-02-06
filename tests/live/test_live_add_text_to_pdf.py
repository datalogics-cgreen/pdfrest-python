from __future__ import annotations

import pytest

from pdfrest import AsyncPdfRestClient, PdfRestApiError, PdfRestClient
from pdfrest.models import PdfRestFile

from ..resources import get_test_resource_path


@pytest.fixture(scope="module")
def uploaded_pdf_for_text(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
) -> PdfRestFile:
    resource = get_test_resource_path("report.pdf")
    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        return client.files.create_from_paths([resource])[0]


def _default_text_object() -> dict[str, object]:
    return {
        "font": "courier",
        "max_width": 200,
        "opacity": 1,
        "page": 1,
        "rotation": 0,
        "text": "Live add text",
        "text_color_rgb": (0, 0, 0),
        "text_size": 14,
        "x": 72,
        "y": 144,
    }


def test_live_add_text_to_pdf(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf_for_text: PdfRestFile,
) -> None:
    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        response = client.add_text_to_pdf(
            uploaded_pdf_for_text,
            text_objects=[_default_text_object()],
            output="live-added-text",
        )

    assert response.output_files
    output_file = response.output_file
    assert output_file.type == "application/pdf"
    assert output_file.name.startswith("live-added-text")
    assert uploaded_pdf_for_text.id in response.input_ids


@pytest.mark.asyncio
async def test_live_async_add_text_to_pdf(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf_for_text: PdfRestFile,
) -> None:
    async with AsyncPdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        response = await client.add_text_to_pdf(
            uploaded_pdf_for_text,
            text_objects=[_default_text_object()],
        )

    assert response.output_files
    output_file = response.output_file
    assert output_file.type == "application/pdf"
    assert uploaded_pdf_for_text.id in response.input_ids


def test_live_add_text_to_pdf_invalid_page(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf_for_text: PdfRestFile,
) -> None:
    with (
        PdfRestClient(
            api_key=pdfrest_api_key,
            base_url=pdfrest_live_base_url,
        ) as client,
        pytest.raises(PdfRestApiError, match=r"(?i)page"),
    ):
        client.add_text_to_pdf(
            uploaded_pdf_for_text,
            text_objects=[_default_text_object()],
            extra_body={
                "text_objects": [
                    {
                        **_default_text_object(),
                        "page": 0,
                    }
                ]
            },
        )


@pytest.mark.asyncio
async def test_live_async_add_text_to_pdf_invalid_page(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf_for_text: PdfRestFile,
) -> None:
    async with AsyncPdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        with pytest.raises(PdfRestApiError, match=r"(?i)page"):
            await client.add_text_to_pdf(
                uploaded_pdf_for_text,
                text_objects=[_default_text_object()],
                extra_body={
                    "text_objects": [
                        {
                            **_default_text_object(),
                            "page": 0,
                        }
                    ]
                },
            )
