from __future__ import annotations

import pytest

from pdfrest import AsyncPdfRestClient, PdfRestApiError, PdfRestClient

BLANK_PDF_LITERAL_CASES = [
    pytest.param(
        "letter",
        "portrait",
        None,
        None,
        "blank-letter",
        id="letter-portrait",
    ),
    pytest.param(
        "legal",
        "landscape",
        None,
        None,
        "blank-legal",
        id="legal-landscape",
    ),
    pytest.param(
        "ledger",
        "portrait",
        None,
        None,
        "blank-ledger",
        id="ledger-portrait",
    ),
    pytest.param(
        "A3",
        "landscape",
        None,
        None,
        "blank-a3",
        id="a3-landscape",
    ),
    pytest.param(
        "A4",
        "portrait",
        None,
        None,
        "blank-a4",
        id="a4-portrait",
    ),
    pytest.param(
        "A5",
        "landscape",
        None,
        None,
        "blank-a5",
        id="a5-landscape",
    ),
    pytest.param(
        "custom",
        None,
        792.0,
        612.0,
        "blank-custom",
        id="custom-dimensions",
    ),
]


@pytest.mark.parametrize(
    ("page_size", "page_orientation", "custom_height", "custom_width", "output_name"),
    BLANK_PDF_LITERAL_CASES,
)
def test_live_blank_pdf_success(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    page_size: str,
    page_orientation: str | None,
    custom_height: float | None,
    custom_width: float | None,
    output_name: str,
) -> None:
    kwargs: dict[str, str | int | float] = {
        "page_size": page_size,
        "page_count": 1,
        "output": output_name,
    }
    if page_orientation is not None:
        kwargs["page_orientation"] = page_orientation
    if custom_height is not None:
        kwargs["custom_height"] = custom_height
    if custom_width is not None:
        kwargs["custom_width"] = custom_width

    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        response = client.blank_pdf(**kwargs)

    assert response.output_files
    output_file = response.output_file
    assert output_file.type == "application/pdf"
    assert output_file.size > 0
    assert response.warning is None
    assert output_file.name.startswith(output_name)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("page_size", "page_orientation", "custom_height", "custom_width", "output_name"),
    BLANK_PDF_LITERAL_CASES,
)
async def test_live_async_blank_pdf_success(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    page_size: str,
    page_orientation: str | None,
    custom_height: float | None,
    custom_width: float | None,
    output_name: str,
) -> None:
    kwargs: dict[str, str | int | float] = {
        "page_size": page_size,
        "page_count": 2,
        "output": output_name,
    }
    if page_orientation is not None:
        kwargs["page_orientation"] = page_orientation
    if custom_height is not None:
        kwargs["custom_height"] = custom_height
    if custom_width is not None:
        kwargs["custom_width"] = custom_width

    async with AsyncPdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        response = await client.blank_pdf(**kwargs)

    assert response.output_files
    output_file = response.output_file
    assert output_file.name.startswith(output_name)
    assert output_file.type == "application/pdf"
    assert output_file.size > 0
    assert response.warning is None


def test_live_blank_pdf_invalid_request(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
) -> None:
    with (
        PdfRestClient(
            api_key=pdfrest_api_key,
            base_url=pdfrest_live_base_url,
        ) as client,
        pytest.raises(PdfRestApiError, match=r"(?i)(page|size)"),
    ):
        client.blank_pdf(
            page_size="letter",
            page_count=1,
            page_orientation="portrait",
            extra_body={"page_size": "not-a-size"},
        )


@pytest.mark.asyncio
async def test_live_async_blank_pdf_invalid_request(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
) -> None:
    async with AsyncPdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        with pytest.raises(PdfRestApiError, match=r"(?i)(page|size)"):
            await client.blank_pdf(
                page_size="letter",
                page_count=1,
                page_orientation="portrait",
                extra_body={"page_size": "bad-size"},
            )
