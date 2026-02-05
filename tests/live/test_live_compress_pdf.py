from __future__ import annotations

from typing import Literal

import pytest

from pdfrest import AsyncPdfRestClient, PdfRestApiError, PdfRestClient
from pdfrest.models import PdfRestFile

from ..resources import get_test_resource_path


@pytest.fixture(scope="module")
def uploaded_pdf_for_compression(
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
def uploaded_compression_profile(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
) -> PdfRestFile:
    resource = get_test_resource_path("compression_profile.json")
    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        return client.files.create_from_paths([resource])[0]


@pytest.mark.parametrize(
    "compression_level",
    [
        pytest.param("low", id="low"),
        pytest.param("medium", id="medium"),
        pytest.param("high", id="high"),
    ],
)
def test_live_compress_pdf_presets(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf_for_compression: PdfRestFile,
    compression_level: Literal["low", "medium", "high"],
) -> None:
    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        response = client.compress_pdf(
            uploaded_pdf_for_compression,
            compression_level=compression_level,
        )

    assert response.output_files
    output_file = response.output_file
    assert output_file.type == "application/pdf"
    assert str(response.input_id) == str(uploaded_pdf_for_compression.id)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "compression_level",
    [
        pytest.param("low", id="low"),
        pytest.param("medium", id="medium"),
        pytest.param("high", id="high"),
    ],
)
async def test_live_async_compress_pdf_presets(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf_for_compression: PdfRestFile,
    compression_level: Literal["low", "medium", "high"],
) -> None:
    async with AsyncPdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        response = await client.compress_pdf(
            uploaded_pdf_for_compression,
            compression_level=compression_level,
        )

    assert response.output_files
    output_file = response.output_file
    assert output_file.type == "application/pdf"
    assert str(response.input_id) == str(uploaded_pdf_for_compression.id)


def test_live_compress_pdf_custom(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf_for_compression: PdfRestFile,
    uploaded_compression_profile: PdfRestFile,
) -> None:
    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        response = client.compress_pdf(
            uploaded_pdf_for_compression,
            compression_level="custom",
            profile=uploaded_compression_profile,
            output="compressed-custom",
        )

    assert (
        response.warning
        == "The document could not be made smaller. No output was produced."
    )
    assert len(response.input_ids) == 2
    assert uploaded_pdf_for_compression.id in response.input_ids
    assert uploaded_compression_profile.id in response.input_ids


@pytest.mark.asyncio
async def test_live_async_compress_pdf_custom(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf_for_compression: PdfRestFile,
    uploaded_compression_profile: PdfRestFile,
) -> None:
    async with AsyncPdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        response = await client.compress_pdf(
            uploaded_pdf_for_compression,
            compression_level="custom",
            profile=uploaded_compression_profile,
            output="compressed-custom",
        )

    assert (
        response.warning
        == "The document could not be made smaller. No output was produced."
    )
    assert len(response.input_ids) == 2
    assert uploaded_pdf_for_compression.id in response.input_ids
    assert uploaded_compression_profile.id in response.input_ids


def test_live_compress_pdf_invalid_level(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf_for_compression: PdfRestFile,
) -> None:
    with (
        PdfRestClient(
            api_key=pdfrest_api_key,
            base_url=pdfrest_live_base_url,
        ) as client,
        pytest.raises(PdfRestApiError, match=r"(?i)compression"),
    ):
        client.compress_pdf(
            uploaded_pdf_for_compression,
            compression_level="low",
            extra_body={"compression_level": "extreme"},
        )


@pytest.mark.asyncio
async def test_live_async_compress_pdf_invalid_level(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf_for_compression: PdfRestFile,
) -> None:
    async with AsyncPdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        with pytest.raises(PdfRestApiError, match=r"(?i)compression"):
            await client.compress_pdf(
                uploaded_pdf_for_compression,
                compression_level="low",
                extra_body={"compression_level": "extreme"},
            )
