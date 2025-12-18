from __future__ import annotations

from typing import cast, get_args

import pytest

from pdfrest import PdfRestApiError, PdfRestClient
from pdfrest.models import PdfRestFile
from pdfrest.types import PdfXType

from ..resources import get_test_resource_path

PDFX_TYPES: tuple[PdfXType, ...] = cast(tuple[PdfXType, ...], get_args(PdfXType))


@pytest.fixture(scope="module")
def uploaded_pdf_for_pdfx(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
) -> PdfRestFile:
    resource = get_test_resource_path("report.pdf")
    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        return client.files.create_from_paths([resource])[0]


@pytest.mark.parametrize("output_type", PDFX_TYPES, ids=list(PDFX_TYPES))
def test_live_convert_to_pdfx_success(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf_for_pdfx: PdfRestFile,
    output_type: PdfXType,
) -> None:
    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        response = client.convert_to_pdfx(
            uploaded_pdf_for_pdfx,
            output_type=output_type,
            output="pdfx-live",
        )

    assert response.output_files
    output_file = response.output_file
    assert output_file.type == "application/pdf"
    assert str(response.input_id) == str(uploaded_pdf_for_pdfx.id)
    assert output_file.name.startswith("pdfx-live")


@pytest.mark.parametrize(
    "invalid_output_type",
    [
        pytest.param("PDF/X-0", id="pdfx-0"),
        pytest.param("PDF/X-99", id="pdfx-99"),
        pytest.param("pdf/x-4", id="lowercase"),
    ],
)
def test_live_convert_to_pdfx_invalid_output_type(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf_for_pdfx: PdfRestFile,
    invalid_output_type: str,
) -> None:
    with (
        PdfRestClient(
            api_key=pdfrest_api_key,
            base_url=pdfrest_live_base_url,
        ) as client,
        pytest.raises(PdfRestApiError),
    ):
        client.convert_to_pdfx(
            uploaded_pdf_for_pdfx,
            output_type="PDF/X-1a",
            extra_body={"output_type": invalid_output_type},
        )
