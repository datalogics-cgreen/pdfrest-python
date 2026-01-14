from __future__ import annotations

import pytest

from pdfrest import AsyncPdfRestClient, PdfRestApiError, PdfRestClient
from pdfrest.models import PdfRestFile

from ..resources import get_test_resource_path


@pytest.fixture(scope="module")
def uploaded_pdf_with_forms(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
) -> PdfRestFile:
    resource = get_test_resource_path("form_with_data.pdf")
    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        return client.files.create_from_paths([resource])[0]


@pytest.mark.parametrize(
    "data_format",
    [
        pytest.param("xml", id="xml"),
        pytest.param("xfdf", id="xfdf"),
    ],
)
def test_live_export_form_data(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf_with_forms: PdfRestFile,
    data_format: str,
) -> None:
    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        response = client.export_form_data(
            uploaded_pdf_with_forms,
            data_format=data_format,  # type: ignore[arg-type]
            output=f"exported-{data_format}",
        )

    assert response.output_files
    output_file = response.output_file
    assert output_file.name.startswith(f"exported-{data_format}")
    assert str(response.input_id) == str(uploaded_pdf_with_forms.id)


@pytest.mark.asyncio
async def test_live_async_export_form_data_success(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf_with_forms: PdfRestFile,
) -> None:
    async with AsyncPdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        response = await client.export_form_data(
            uploaded_pdf_with_forms,
            data_format="xml",
            output="async-exported",
        )

    assert response.output_files
    output_file = response.output_file
    assert output_file.name.startswith("async-exported")
    assert str(response.input_id) == str(uploaded_pdf_with_forms.id)


def test_live_export_form_data_invalid_format_for_pdf_type(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf_with_forms: PdfRestFile,
) -> None:
    with (
        PdfRestClient(
            api_key=pdfrest_api_key,
            base_url=pdfrest_live_base_url,
        ) as client,
        pytest.raises(PdfRestApiError, match=r"(?i)data_format"),
    ):
        client.export_form_data(
            uploaded_pdf_with_forms,
            data_format="xdp",  # type: ignore[arg-type]
        )


@pytest.mark.asyncio
async def test_live_async_export_form_data_invalid_format_for_pdf_type(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf_with_forms: PdfRestFile,
) -> None:
    async with AsyncPdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        with pytest.raises(PdfRestApiError, match=r"(?i)data_format"):
            await client.export_form_data(
                uploaded_pdf_with_forms,
                data_format="xdp",  # type: ignore[arg-type]
            )
