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


@pytest.fixture(scope="module")
def uploaded_form_data_file(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
) -> PdfRestFile:
    resource = get_test_resource_path("form_data.xml")
    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        return client.files.create_from_paths([resource])[0]


@pytest.mark.parametrize(
    "output_name",
    [
        pytest.param(None, id="default-output"),
        pytest.param("imported-form", id="custom-output"),
    ],
)
def test_live_import_form_data(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf_with_forms: PdfRestFile,
    uploaded_form_data_file: PdfRestFile,
    output_name: str | None,
) -> None:
    kwargs: dict[str, str] = {}
    if output_name is not None:
        kwargs["output"] = output_name

    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        response = client.import_form_data(
            uploaded_pdf_with_forms,
            uploaded_form_data_file,
            **kwargs,
        )

    assert response.output_files
    output_file = response.output_file
    assert output_file.type == "application/pdf"
    assert str(response.input_id) == str(uploaded_pdf_with_forms.id)
    if output_name is not None:
        assert output_file.name.startswith(output_name)
    else:
        assert output_file.name.endswith(".pdf")


@pytest.mark.asyncio
async def test_live_async_import_form_data_success(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf_with_forms: PdfRestFile,
    uploaded_form_data_file: PdfRestFile,
) -> None:
    async with AsyncPdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        response = await client.import_form_data(
            uploaded_pdf_with_forms,
            uploaded_form_data_file,
            output="async-imported",
        )

    assert response.output_files
    output_file = response.output_file
    assert output_file.name.startswith("async-imported")
    assert output_file.type == "application/pdf"
    assert str(response.input_id) == str(uploaded_pdf_with_forms.id)


def test_live_import_form_data_invalid_data_file_id(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf_with_forms: PdfRestFile,
    uploaded_form_data_file: PdfRestFile,
) -> None:
    with (
        PdfRestClient(
            api_key=pdfrest_api_key,
            base_url=pdfrest_live_base_url,
        ) as client,
        pytest.raises(PdfRestApiError, match=r"(?i)(data|id)"),
    ):
        client.import_form_data(
            uploaded_pdf_with_forms,
            uploaded_form_data_file,
            extra_body={"data_file_id": "ffffffff-ffff-ffff-ffff-ffffffffffff"},
        )


@pytest.mark.asyncio
async def test_live_async_import_form_data_invalid_data_file_id(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf_with_forms: PdfRestFile,
    uploaded_form_data_file: PdfRestFile,
) -> None:
    async with AsyncPdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        with pytest.raises(PdfRestApiError, match=r"(?i)(data|id)"):
            await client.import_form_data(
                uploaded_pdf_with_forms,
                uploaded_form_data_file,
                extra_body={"data_file_id": "00000000-0000-0000-0000-000000000000"},
            )
