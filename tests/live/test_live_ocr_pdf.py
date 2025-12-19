from __future__ import annotations

import pytest

from pdfrest import PdfRestApiError, PdfRestClient
from pdfrest.models import PdfRestFileBasedResponse

from ..resources import get_test_resource_path


def test_live_ocr_pdf_success(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
) -> None:
    resource = get_test_resource_path("report.pdf")
    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        uploaded = client.files.create_from_paths([resource])[0]
        response = client.ocr_pdf(uploaded)

    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.output_files
    assert response.output_file.id
    assert response.input_id == uploaded.id


def test_live_ocr_pdf_invalid_pages(
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
            client.ocr_pdf(
                uploaded,
                extra_body={"pages": "last-1"},
            )
