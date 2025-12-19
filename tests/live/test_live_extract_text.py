from __future__ import annotations

import pytest

from pdfrest import PdfRestApiError, PdfRestClient
from pdfrest.models import ExtractTextResponse

from ..resources import get_test_resource_path


def test_live_extract_text_success(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
) -> None:
    resource = get_test_resource_path("report.pdf")
    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        uploaded = client.files.create_from_paths([resource])[0]
        response = client.extract_text(
            uploaded,
            output_type="json",
            full_text="document",
            preserve_line_breaks="on",
            word_style="off",
            word_coordinates="off",
        )

    assert isinstance(response, ExtractTextResponse)
    assert response.text
    assert response.input_id == uploaded.id


def test_live_extract_text_invalid_pages(
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
            client.extract_text(
                uploaded,
                extra_body={"pages": "last-1"},
                output_type="json",
            )
