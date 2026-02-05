from __future__ import annotations

import pytest

from pdfrest import AsyncPdfRestClient, PdfRestApiError, PdfRestClient
from pdfrest.models import PdfRestFile

from ..resources import get_test_resource_path


@pytest.fixture(scope="module")
def uploaded_pdf_for_rasterize(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
) -> PdfRestFile:
    resource = get_test_resource_path("report.pdf")
    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        return client.files.create_from_paths([resource])[0]


@pytest.mark.parametrize(
    "output_name",
    [
        pytest.param(None, id="default-output"),
        pytest.param("rasterized-live", id="custom-output"),
    ],
)
def test_live_rasterize_pdf_success(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf_for_rasterize: PdfRestFile,
    output_name: str | None,
) -> None:
    kwargs: dict[str, str] = {}
    if output_name is not None:
        kwargs["output"] = output_name

    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        response = client.rasterize_pdf(uploaded_pdf_for_rasterize, **kwargs)

    assert response.output_files
    output_file = response.output_file
    assert output_file.type == "application/pdf"
    assert output_file.size > 0
    assert response.warning is None
    assert str(response.input_id) == str(uploaded_pdf_for_rasterize.id)
    if output_name is not None:
        assert output_file.name.startswith(output_name)
    else:
        assert output_file.name.endswith(".pdf")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "output_name",
    [
        pytest.param(None, id="default-output"),
        pytest.param("rasterized-live", id="custom-output"),
    ],
)
async def test_live_async_rasterize_pdf_success(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf_for_rasterize: PdfRestFile,
    output_name: str | None,
) -> None:
    kwargs: dict[str, str] = {}
    if output_name is not None:
        kwargs["output"] = output_name

    async with AsyncPdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        response = await client.rasterize_pdf(uploaded_pdf_for_rasterize, **kwargs)

    assert response.output_files
    output_file = response.output_file
    if output_name is not None:
        assert output_file.name.startswith(output_name)
    else:
        assert output_file.name.endswith(".pdf")
    assert output_file.type == "application/pdf"
    assert output_file.size > 0
    assert response.warning is None
    assert str(response.input_id) == str(uploaded_pdf_for_rasterize.id)


def test_live_rasterize_pdf_invalid_file_id(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf_for_rasterize: PdfRestFile,
) -> None:
    with (
        PdfRestClient(
            api_key=pdfrest_api_key,
            base_url=pdfrest_live_base_url,
        ) as client,
        pytest.raises(PdfRestApiError, match=r"(?i)(id|file)"),
    ):
        client.rasterize_pdf(
            uploaded_pdf_for_rasterize,
            extra_body={"id": "00000000-0000-0000-0000-000000000000"},
        )


@pytest.mark.asyncio
async def test_live_async_rasterize_pdf_invalid_file_id(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf_for_rasterize: PdfRestFile,
) -> None:
    async with AsyncPdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        with pytest.raises(PdfRestApiError, match=r"(?i)(id|file)"):
            await client.rasterize_pdf(
                uploaded_pdf_for_rasterize,
                extra_body={"id": "ffffffff-ffff-ffff-ffff-ffffffffffff"},
            )
