from __future__ import annotations

import pytest

from pdfrest import AsyncPdfRestClient, PdfRestApiError, PdfRestClient
from pdfrest.models import PdfRestFile

from ..resources import get_test_resource_path

IMPORT_FORM_DATA_SUCCESS_CASES = (
    pytest.param(
        ("acroform.pdf", "test-data-acro.xml", None),
        id="acro-xml",
    ),
    pytest.param(
        ("acroform.pdf", "test-data-acro.xfdf", None),
        id="acro-xfdf",
    ),
    pytest.param(
        ("xfa.pdf", "test-data-xfa.xml", None),
        id="xfa-xml",
    ),
    pytest.param(
        ("xfa.pdf", "test-data-xfa.xdp", None),
        id="xfa-xdp",
    ),
    pytest.param(
        (
            "xfa.pdf",
            "test-data-xfa.xfd",
            "application/vnd.adobe.xfd+xml",
        ),
        id="xfa-xfd",
    ),
)


@pytest.fixture(scope="module", params=IMPORT_FORM_DATA_SUCCESS_CASES)
def uploaded_success_import_form_data_case(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    request: pytest.FixtureRequest,
) -> tuple[PdfRestFile, PdfRestFile]:
    pdf_resource_name, data_resource_name, forced_data_mime = request.param
    pdf_resource = get_test_resource_path(pdf_resource_name)
    data_resource = get_test_resource_path(data_resource_name)

    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        input_file = client.files.create_from_paths([pdf_resource])[0]
        data_file = client.files.create_from_paths([data_resource])[0]

    # pdfRest currently reports .xfd uploads as application/octet-stream.
    # Override the local MIME metadata so the request can exercise xfd imports.
    if forced_data_mime is not None:
        data_file = data_file.model_copy(update={"type": forced_data_mime})

    return input_file, data_file


@pytest.fixture(scope="module")
def uploaded_acro_import_pair(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
) -> tuple[PdfRestFile, PdfRestFile]:
    acro_pdf = get_test_resource_path("acroform.pdf")
    acro_data = get_test_resource_path("test-data-acro.xml")

    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        input_file = client.files.create_from_paths([acro_pdf])[0]
        data_file = client.files.create_from_paths([acro_data])[0]

    return input_file, data_file


@pytest.fixture(scope="module")
def uploaded_acro_fdf_import_pair(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
) -> tuple[PdfRestFile, PdfRestFile]:
    acro_pdf = get_test_resource_path("acroform.pdf")
    acro_fdf = get_test_resource_path("test-data-acro.fdf")

    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        input_file = client.files.create_from_paths([acro_pdf])[0]
        data_file = client.files.create_from_paths([acro_fdf])[0]

    return input_file, data_file


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
    uploaded_success_import_form_data_case: tuple[PdfRestFile, PdfRestFile],
    output_name: str | None,
) -> None:
    kwargs: dict[str, str] = {}
    if output_name is not None:
        kwargs["output"] = output_name

    uploaded_pdf_with_forms, uploaded_form_data_file = (
        uploaded_success_import_form_data_case
    )

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
    assert output_file.size > 0
    assert response.warning is None
    assert str(uploaded_pdf_with_forms.id) in {
        str(file_id) for file_id in response.input_ids
    }
    assert str(uploaded_form_data_file.id) in {
        str(file_id) for file_id in response.input_ids
    }
    if output_name is not None:
        assert output_file.name.startswith(output_name)
    else:
        assert output_file.name.endswith(".pdf")


@pytest.mark.asyncio
async def test_live_async_import_form_data_success(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_success_import_form_data_case: tuple[PdfRestFile, PdfRestFile],
) -> None:
    uploaded_pdf_with_forms, uploaded_form_data_file = (
        uploaded_success_import_form_data_case
    )

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
    assert output_file.size > 0
    assert response.warning is None
    assert str(uploaded_pdf_with_forms.id) in {
        str(file_id) for file_id in response.input_ids
    }
    assert str(uploaded_form_data_file.id) in {
        str(file_id) for file_id in response.input_ids
    }


def test_live_import_form_data_fdf_server_error(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_acro_fdf_import_pair: tuple[PdfRestFile, PdfRestFile],
) -> None:
    uploaded_pdf_with_forms, uploaded_form_data_file = uploaded_acro_fdf_import_pair

    with (
        PdfRestClient(
            api_key=pdfrest_api_key,
            base_url=pdfrest_live_base_url,
        ) as client,
        pytest.raises(
            PdfRestApiError,
            match=r"(?i)(issue processing|filled correctly|corrupted)",
        ),
    ):
        client.import_form_data(uploaded_pdf_with_forms, uploaded_form_data_file)


@pytest.mark.asyncio
async def test_live_async_import_form_data_fdf_server_error(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_acro_fdf_import_pair: tuple[PdfRestFile, PdfRestFile],
) -> None:
    uploaded_pdf_with_forms, uploaded_form_data_file = uploaded_acro_fdf_import_pair

    async with AsyncPdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        with pytest.raises(
            PdfRestApiError,
            match=r"(?i)(issue processing|filled correctly|corrupted)",
        ):
            await client.import_form_data(
                uploaded_pdf_with_forms, uploaded_form_data_file
            )


def test_live_import_form_data_invalid_data_file_id(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_acro_import_pair: tuple[PdfRestFile, PdfRestFile],
) -> None:
    uploaded_pdf_with_forms, uploaded_form_data_file = uploaded_acro_import_pair

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
    uploaded_acro_import_pair: tuple[PdfRestFile, PdfRestFile],
) -> None:
    uploaded_pdf_with_forms, uploaded_form_data_file = uploaded_acro_import_pair

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
