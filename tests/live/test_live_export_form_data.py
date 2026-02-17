from __future__ import annotations

import pytest

from pdfrest import AsyncPdfRestClient, PdfRestApiError, PdfRestClient
from pdfrest.models import PdfRestFile
from pdfrest.types import ExportDataFormat

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
        pytest.param("fdf", id="fdf"),
        pytest.param("xfdf", id="xfdf"),
        pytest.param("xml", id="xml"),
    ],
)
def test_live_export_form_data_acroform(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf_with_forms: PdfRestFile,
    data_format: ExportDataFormat,
) -> None:
    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        response = client.export_form_data(
            uploaded_pdf_with_forms,
            data_format=data_format,
            output=f"exported-{data_format}",
        )

    assert response.output_files
    output_file = response.output_file
    assert output_file.name.startswith(f"exported-{data_format}")
    assert output_file.type
    assert output_file.size > 0
    assert response.warning is None
    assert str(uploaded_pdf_with_forms.id) in {
        str(file_id) for file_id in response.input_ids
    }


@pytest.fixture(scope="module")
def uploaded_xfa_pdf(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
) -> PdfRestFile:
    resource = get_test_resource_path("xfa.pdf")
    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        return client.files.create_from_paths([resource])[0]


@pytest.mark.parametrize(
    "data_format",
    [
        pytest.param("xfd", id="xfd"),
        pytest.param("xdp", id="xdp"),
        pytest.param("xml", id="xml"),
    ],
)
def test_live_export_form_data_xfa(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_xfa_pdf: PdfRestFile,
    data_format: ExportDataFormat,
) -> None:
    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        response = client.export_form_data(
            uploaded_xfa_pdf,
            data_format=data_format,
            output=f"exported-xfa-{data_format}",
        )

    assert response.output_files
    output_file = response.output_file
    assert output_file.name.startswith(f"exported-xfa-{data_format}")
    assert output_file.type
    assert output_file.size > 0
    assert response.warning is None
    assert str(uploaded_xfa_pdf.id) in {str(file_id) for file_id in response.input_ids}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "data_format",
    [
        pytest.param("fdf", id="fdf"),
        pytest.param("xfdf", id="xfdf"),
        pytest.param("xml", id="xml"),
    ],
)
async def test_live_async_export_form_data_acroform(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf_with_forms: PdfRestFile,
    data_format: ExportDataFormat,
) -> None:
    async with AsyncPdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        response = await client.export_form_data(
            uploaded_pdf_with_forms,
            data_format=data_format,
            output=f"async-acro-{data_format}",
        )

    assert response.output_files
    output_file = response.output_file
    assert output_file.name.startswith(f"async-acro-{data_format}")
    assert output_file.type
    assert output_file.size > 0
    assert response.warning is None
    assert str(uploaded_pdf_with_forms.id) in {
        str(file_id) for file_id in response.input_ids
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "data_format",
    [
        pytest.param("xfd", id="xfd"),
        pytest.param("xdp", id="xdp"),
        pytest.param("xml", id="xml"),
    ],
)
async def test_live_async_export_form_data_xfa(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_xfa_pdf: PdfRestFile,
    data_format: ExportDataFormat,
) -> None:
    async with AsyncPdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        response = await client.export_form_data(
            uploaded_xfa_pdf,
            data_format=data_format,
            output=f"async-xfa-{data_format}",
        )

    assert response.output_files
    output_file = response.output_file
    assert output_file.name.startswith(f"async-xfa-{data_format}")
    assert output_file.type
    assert output_file.size > 0
    assert response.warning is None
    assert str(uploaded_xfa_pdf.id) in {str(file_id) for file_id in response.input_ids}


@pytest.mark.parametrize(
    "invalid_format",
    [
        pytest.param("xdp", id="xdp"),
        pytest.param("xfd", id="xfd"),
    ],
)
def test_live_export_form_data_invalid_format_for_pdf_type(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf_with_forms: PdfRestFile,
    invalid_format: ExportDataFormat,
) -> None:
    with (
        PdfRestClient(
            api_key=pdfrest_api_key,
            base_url=pdfrest_live_base_url,
        ) as client,
        pytest.raises(PdfRestApiError, match=r"(?i)(acroform|data_format)"),
    ):
        client.export_form_data(
            uploaded_pdf_with_forms,
            data_format=invalid_format,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "invalid_format",
    [
        pytest.param("xdp", id="xdp"),
        pytest.param("xfd", id="xfd"),
    ],
)
async def test_live_async_export_form_data_invalid_format_for_pdf_type(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf_with_forms: PdfRestFile,
    invalid_format: ExportDataFormat,
) -> None:
    async with AsyncPdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        with pytest.raises(PdfRestApiError, match=r"(?i)(acroform|data_format)"):
            await client.export_form_data(
                uploaded_pdf_with_forms,
                data_format=invalid_format,
            )


@pytest.mark.parametrize(
    "invalid_format",
    [
        pytest.param("xfdf", id="xfdf"),
        pytest.param("fdf", id="fdf"),
    ],
)
def test_live_export_form_data_invalid_format_for_xfa(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_xfa_pdf: PdfRestFile,
    invalid_format: ExportDataFormat,
) -> None:
    with (
        PdfRestClient(
            api_key=pdfrest_api_key,
            base_url=pdfrest_live_base_url,
        ) as client,
        pytest.raises(PdfRestApiError, match=r"(?i)(xfa|data_format)"),
    ):
        client.export_form_data(
            uploaded_xfa_pdf,
            data_format=invalid_format,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "invalid_format",
    [
        pytest.param("xfdf", id="xfdf"),
        pytest.param("fdf", id="fdf"),
    ],
)
async def test_live_async_export_form_data_invalid_format_for_xfa(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_xfa_pdf: PdfRestFile,
    invalid_format: ExportDataFormat,
) -> None:
    async with AsyncPdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        with pytest.raises(PdfRestApiError, match=r"(?i)(xfa|data_format)"):
            await client.export_form_data(
                uploaded_xfa_pdf,
                data_format=invalid_format,
            )
