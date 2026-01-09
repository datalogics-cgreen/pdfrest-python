from __future__ import annotations

import pytest

from pdfrest import AsyncPdfRestClient, PdfRestApiError, PdfRestClient
from pdfrest.models import PdfRestFileBasedResponse, SummarizePdfTextResponse

from ..resources import get_test_resource_path


def test_live_summarize_text_success(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
) -> None:
    resource = get_test_resource_path("report.pdf")
    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        uploaded = client.files.create_from_paths([resource])[0]
        response = client.summarize_text(
            uploaded,
            target_word_count=40,
            summary_format="overview",
        )

    assert isinstance(response, SummarizePdfTextResponse)
    assert response.summary
    assert response.input_id == uploaded.id


def test_live_summarize_text_to_file_success(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
) -> None:
    resource = get_test_resource_path("report.pdf")
    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        uploaded = client.files.create_from_paths([resource])[0]
        response = client.summarize_text_to_file(
            uploaded,
            target_word_count=40,
            summary_format="overview",
        )

    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.output_files
    output_file = response.output_file
    assert output_file.name.endswith(".md")
    assert output_file.type == "text/markdown"
    assert output_file.size > 0
    assert response.warning is None
    assert response.input_id == uploaded.id


@pytest.mark.asyncio
async def test_live_async_summarize_text_success(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
) -> None:
    resource = get_test_resource_path("report.pdf")
    async with AsyncPdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        uploaded = (await client.files.create_from_paths([resource]))[0]
        response = await client.summarize_text(
            uploaded,
            target_word_count=30,
            summary_format="overview",
        )

    assert isinstance(response, SummarizePdfTextResponse)
    assert response.summary
    assert response.input_id == uploaded.id


def test_live_summarize_text_invalid_format(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
) -> None:
    resource = get_test_resource_path("report.pdf")
    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        uploaded = client.files.create_from_paths([resource])[0]
        with pytest.raises(PdfRestApiError, match=r"(?i)summary"):
            client.summarize_text(
                uploaded,
                extra_body={"summary_format": "invalid-style"},
            )


@pytest.mark.asyncio
async def test_live_async_summarize_text_invalid_format(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
) -> None:
    resource = get_test_resource_path("report.pdf")
    async with AsyncPdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        uploaded = (await client.files.create_from_paths([resource]))[0]
        with pytest.raises(PdfRestApiError, match=r"(?i)summary"):
            await client.summarize_text(
                uploaded,
                extra_body={"summary_format": "invalid-style"},
            )
