from __future__ import annotations

import pytest

from pdfrest import AsyncPdfRestClient, PdfRestApiError, PdfRestClient
from pdfrest.models import PdfRestFile

from ..resources import get_test_resource_path


@pytest.fixture(scope="module")
def uploaded_pdf_for_watermark(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
) -> PdfRestFile:
    resource = get_test_resource_path("report.pdf")
    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        return client.files.create_from_paths([resource])[0]


@pytest.fixture(scope="module")
def uploaded_watermark_pdf(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
) -> PdfRestFile:
    resource = get_test_resource_path("duckhat.pdf")
    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        return client.files.create_from_paths([resource])[0]


@pytest.mark.parametrize(
    "output_name",
    [
        pytest.param(None, id="default-output"),
        pytest.param("watermark-text", id="custom-output"),
    ],
)
def test_live_watermark_pdf_text_success(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf_for_watermark: PdfRestFile,
    output_name: str | None,
) -> None:
    kwargs: dict[str, str] = {}
    if output_name is not None:
        kwargs["output"] = output_name

    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        response = client.watermark_pdf_with_text(
            uploaded_pdf_for_watermark,
            watermark_text="CONFIDENTIAL",
            opacity=0.6,
            pages=["1", "last"],
            **kwargs,
        )

    output_file = response.output_file
    assert output_file.type == "application/pdf"
    assert output_file.size > 0
    assert str(response.input_id) == str(uploaded_pdf_for_watermark.id)
    if output_name is not None:
        assert output_file.name.startswith(output_name)
    else:
        assert output_file.name.endswith(".pdf")


def test_live_watermark_pdf_image_success(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf_for_watermark: PdfRestFile,
    uploaded_watermark_pdf: PdfRestFile,
) -> None:
    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        response = client.watermark_pdf_with_image(
            uploaded_pdf_for_watermark,
            watermark_file=uploaded_watermark_pdf,
            watermark_file_scale=0.75,
            behind_page=True,
            output="watermark-file",
        )

    output_file = response.output_file
    assert output_file.type == "application/pdf"
    assert output_file.size > 0
    assert output_file.name.startswith("watermark-file")
    assert [str(value) for value in response.input_ids] == [
        str(uploaded_pdf_for_watermark.id),
        str(uploaded_watermark_pdf.id),
    ]


@pytest.mark.asyncio
async def test_live_async_watermark_pdf_text_success(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf_for_watermark: PdfRestFile,
) -> None:
    async with AsyncPdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        response = await client.watermark_pdf_with_text(
            uploaded_pdf_for_watermark,
            watermark_text="ASYNC",
            horizontal_alignment="right",
            vertical_alignment="top",
            x=-36,
            y=36,
            output="async-watermark",
        )

    output_file = response.output_file
    assert output_file.name.startswith("async-watermark")
    assert output_file.type == "application/pdf"
    assert output_file.size > 0
    assert str(response.input_id) == str(uploaded_pdf_for_watermark.id)


def test_live_watermark_pdf_invalid_alignment(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf_for_watermark: PdfRestFile,
) -> None:
    with (
        PdfRestClient(
            api_key=pdfrest_api_key,
            base_url=pdfrest_live_base_url,
        ) as client,
        pytest.raises(PdfRestApiError, match=r"(?i)alignment"),
    ):
        client.watermark_pdf_with_text(
            uploaded_pdf_for_watermark,
            watermark_text="BadAlignment",
            extra_body={"horizontal_alignment": "diagonal"},
        )


@pytest.mark.asyncio
async def test_live_async_watermark_pdf_invalid_file_id(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf_for_watermark: PdfRestFile,
) -> None:
    async with AsyncPdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        with pytest.raises(PdfRestApiError, match=r"(?i)(id|file)"):
            await client.watermark_pdf_with_text(
                uploaded_pdf_for_watermark,
                watermark_text="AsyncInvalid",
                extra_body={"id": "00000000-0000-0000-0000-000000000000"},
            )
