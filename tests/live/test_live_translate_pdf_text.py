from __future__ import annotations

import pytest

from pdfrest import AsyncPdfRestClient, PdfRestApiError, PdfRestClient
from pdfrest.models import (
    TranslatePdfTextFileResponse,
    TranslatePdfTextResponse,
)

from ..resources import get_test_resource_path


def test_live_translate_pdf_text_success(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
) -> None:
    resource = get_test_resource_path("report.pdf")
    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        uploaded = client.files.create_from_paths([resource])[0]
        response = client.translate_pdf_text(
            uploaded,
            output_language="fr",
            output_format="plaintext",
        )

    assert isinstance(response, TranslatePdfTextResponse)
    assert response.translated_text
    assert response.output_language == "fr"
    assert response.source_languages
    assert response.input_id == uploaded.id


@pytest.mark.asyncio
async def test_live_async_translate_pdf_text_success(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
) -> None:
    resource = get_test_resource_path("report.pdf")
    async with AsyncPdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        uploaded = (await client.files.create_from_paths([resource]))[0]
        response = await client.translate_pdf_text(
            uploaded,
            output_language="es",
            output_format="plaintext",
        )

    assert isinstance(response, TranslatePdfTextResponse)
    assert response.translated_text
    assert response.output_language == "es"
    assert response.input_id == uploaded.id


def test_live_translate_pdf_text_invalid_output_format(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
) -> None:
    resource = get_test_resource_path("report.pdf")
    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        uploaded = client.files.create_from_paths([resource])[0]
        with pytest.raises(
            PdfRestApiError,
            match=r"invalid-format is not a valid input for 'output_format'",
        ):
            client.translate_pdf_text(
                uploaded,
                output_language="es",
                extra_body={"output_format": "invalid-format"},
            )


@pytest.mark.asyncio
async def test_live_async_translate_pdf_text_invalid_output_format(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
) -> None:
    resource = get_test_resource_path("report.pdf")
    async with AsyncPdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        uploaded = (await client.files.create_from_paths([resource]))[0]
        with pytest.raises(
            PdfRestApiError,
            match=r"invalid-format is not a valid input for 'output_format'",
        ):
            await client.translate_pdf_text(
                uploaded,
                output_language="de",
                extra_body={"output_format": "invalid-format"},
            )


def test_live_translate_pdf_text_file_success(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
) -> None:
    resource = get_test_resource_path("report.pdf")
    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        uploaded = client.files.create_from_paths([resource])[0]
        response = client.translate_pdf_text_to_file(
            uploaded,
            output_language="fr",
            output_format="plaintext",
        )

    assert isinstance(response, TranslatePdfTextFileResponse)
    assert response.output_files
    output_file = response.output_file
    assert output_file.name.endswith(".txt")
    assert output_file.type == "text/plain"
    assert output_file.size > 0
    assert response.warning is None
    assert response.output_language == "fr"
    assert response.source_languages
    assert response.input_id == uploaded.id
