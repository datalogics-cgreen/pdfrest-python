from __future__ import annotations

import pytest

from pdfrest import PdfRestApiError, PdfRestClient
from pdfrest.models import PdfRestFileBasedResponse, SummarizePdfTextResponse

from ..resources import get_test_resource_path


def test_live_summarize_pdf_text_success(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
) -> None:
    resource = get_test_resource_path("report.pdf")
    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        uploaded = client.files.create_from_paths([resource])[0]
        response = client.summarize_pdf_text(
            uploaded,
            target_word_count=40,
            summary_format="overview",
        )

    assert isinstance(response, SummarizePdfTextResponse)
    assert response.summary
    assert response.input_id == uploaded.id


def test_live_summarize_pdf_text_to_file_success(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
) -> None:
    resource = get_test_resource_path("report.pdf")
    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        uploaded = client.files.create_from_paths([resource])[0]
        response = client.summarize_pdf_text_to_file(
            uploaded,
            target_word_count=40,
            summary_format="overview",
        )

    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.output_files
    assert response.output_file.id
    assert response.input_id == uploaded.id


def test_live_summarize_pdf_text_invalid_format(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
) -> None:
    resource = get_test_resource_path("report.pdf")
    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        uploaded = client.files.create_from_paths([resource])[0]
        with pytest.raises(PdfRestApiError, match="error"):
            client.summarize_pdf_text(
                uploaded,
                extra_body={"summary_format": "invalid-style"},
            )
