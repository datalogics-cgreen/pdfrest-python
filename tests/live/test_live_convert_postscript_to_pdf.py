from __future__ import annotations

import pytest

from pdfrest import AsyncPdfRestClient, PdfRestApiError, PdfRestClient
from pdfrest.models import PdfRestFile

from ..resources import get_test_resource_path


@pytest.fixture(scope="module")
def uploaded_postscript_for_pdf(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
) -> PdfRestFile:
    resource = get_test_resource_path("sample.eps")
    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        return client.files.create_from_paths([resource])[0]


@pytest.mark.parametrize(
    ("output_name", "compression", "downsample"),
    [
        pytest.param(None, None, None, id="defaults"),
        pytest.param("live-postscript", "lossy", 300, id="customized"),
    ],
)
def test_live_convert_postscript_to_pdf_success(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_postscript_for_pdf: PdfRestFile,
    output_name: str | None,
    compression: str | None,
    downsample: int | None,
) -> None:
    kwargs: dict[str, object] = {}
    if output_name is not None:
        kwargs["output"] = output_name
    if compression is not None:
        kwargs["compression"] = compression
    if downsample is not None:
        kwargs["downsample"] = downsample

    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        response = client.convert_postscript_to_pdf(
            uploaded_postscript_for_pdf,
            **kwargs,
        )

    assert response.output_files
    output_file = response.output_file
    assert output_file.type == "application/pdf"
    assert output_file.size > 0
    assert response.warning is None
    assert str(response.input_id) == str(uploaded_postscript_for_pdf.id)
    if output_name is not None:
        assert output_file.name.startswith(output_name)
    else:
        assert output_file.name.endswith(".pdf")


@pytest.mark.asyncio
async def test_live_async_convert_postscript_to_pdf_success(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_postscript_for_pdf: PdfRestFile,
) -> None:
    async with AsyncPdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        response = await client.convert_postscript_to_pdf(
            uploaded_postscript_for_pdf,
            output="live-postscript-async",
            compression="lossless",
        )

    assert response.output_files
    output_file = response.output_file
    assert output_file.type == "application/pdf"
    assert output_file.size > 0
    assert response.warning is None
    assert str(response.input_id) == str(uploaded_postscript_for_pdf.id)
    assert output_file.name.startswith("live-postscript-async")


def test_live_convert_postscript_to_pdf_invalid_downsample(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_postscript_for_pdf: PdfRestFile,
) -> None:
    with (
        PdfRestClient(
            api_key=pdfrest_api_key,
            base_url=pdfrest_live_base_url,
        ) as client,
        pytest.raises(PdfRestApiError, match=r"(?i)downsample"),
    ):
        client.convert_postscript_to_pdf(
            uploaded_postscript_for_pdf,
            extra_body={"downsample": 0},
        )
