from __future__ import annotations

import pytest

from pdfrest import PdfRestApiError, PdfRestClient
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
    "output_name",
    [
        pytest.param(None, id="default-output"),
        pytest.param("flattened-live", id="custom-output"),
    ],
)
def test_live_flatten_pdf_forms(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf_with_forms: PdfRestFile,
    output_name: str | None,
) -> None:
    kwargs: dict[str, str] = {}
    if output_name is not None:
        kwargs["output"] = output_name

    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        response = client.flatten_pdf_forms(uploaded_pdf_with_forms, **kwargs)

    assert response.output_files
    output_file = response.output_file
    assert output_file.type == "application/pdf"
    assert str(response.input_id) == str(uploaded_pdf_with_forms.id)
    if output_name is not None:
        assert output_file.name.startswith(output_name)
    else:
        assert output_file.name.endswith(".pdf")


def test_live_flatten_pdf_forms_invalid_file_id(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf_with_forms: PdfRestFile,
) -> None:
    with (
        PdfRestClient(
            api_key=pdfrest_api_key,
            base_url=pdfrest_live_base_url,
        ) as client,
        pytest.raises(PdfRestApiError),
    ):
        client.flatten_pdf_forms(
            uploaded_pdf_with_forms,
            extra_body={"id": "ffffffff-ffff-ffff-ffff-ffffffffffff"},
        )
