from __future__ import annotations

import pytest

from pdfrest import PdfRestApiError, PdfRestClient
from pdfrest.models import TranslatePdfTextResponse

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
            target_language="fr",
            output_type="json",
            output_format="plaintext",
        )

    assert isinstance(response, TranslatePdfTextResponse)
    assert response.translation
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
        with pytest.raises(PdfRestApiError, match="error"):
            client.translate_pdf_text(
                uploaded,
                target_language="es",
                extra_body={"output_format": "invalid-format"},
            )
