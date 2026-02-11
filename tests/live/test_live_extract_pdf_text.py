from __future__ import annotations

from itertools import product

import pytest

from pdfrest import AsyncPdfRestClient, PdfRestApiError, PdfRestClient
from pdfrest.models import ExtractedTextDocument

from ..resources import get_test_resource_path

FULL_TEXT_OPTIONS = ("off", "by_page", "document")
BOOL_OPTION_SETS = list(product([False, True], repeat=3))

LIVE_OPTION_SETS = [
    pytest.param(
        {
            "full_text": full_text,
            "preserve_line_breaks": preserve,
            "word_style": word_style,
            "word_coordinates": word_coordinates,
        },
        id=f"{full_text}-plb-{int(preserve)}-ws-{int(word_style)}-wc-{int(word_coordinates)}",
    )
    for full_text in FULL_TEXT_OPTIONS
    for preserve, word_style, word_coordinates in BOOL_OPTION_SETS
]


def _assert_live_full_text(
    response: ExtractedTextDocument,
    *,
    full_text_mode: str,
) -> None:
    if full_text_mode == "off":
        assert response.full_text is None
    elif full_text_mode == "document":
        assert response.full_text is not None
        assert response.full_text.document_text is not None
    else:
        assert response.full_text is not None
        assert response.full_text.pages is not None


@pytest.mark.parametrize("options", LIVE_OPTION_SETS)
def test_live_extract_pdf_text_success(
    options: dict[str, bool | str],
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
) -> None:
    resource = get_test_resource_path("report.pdf")
    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        uploaded = client.files.create_from_paths([resource])[0]
        response = client.extract_pdf_text(uploaded, **options)

    assert isinstance(response, ExtractedTextDocument)
    assert response.input_id == uploaded.id
    _assert_live_full_text(response, full_text_mode=options["full_text"])
    if options["word_style"] or options["word_coordinates"]:
        assert response.words is not None
        assert response.words


@pytest.mark.asyncio
@pytest.mark.parametrize("options", LIVE_OPTION_SETS)
async def test_live_async_extract_pdf_text_success(
    options: dict[str, bool | str],
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
) -> None:
    resource = get_test_resource_path("report.pdf")
    async with AsyncPdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        uploaded = (await client.files.create_from_paths([resource]))[0]
        response = await client.extract_pdf_text(uploaded, **options)

    assert isinstance(response, ExtractedTextDocument)
    assert response.input_id == uploaded.id
    _assert_live_full_text(response, full_text_mode=options["full_text"])
    if options["word_style"] or options["word_coordinates"]:
        assert response.words is not None
        assert response.words


def test_live_extract_pdf_text_invalid_pages(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
) -> None:
    resource = get_test_resource_path("report.pdf")
    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        uploaded = client.files.create_from_paths([resource])[0]
        with pytest.raises(PdfRestApiError, match=r"(?i)page"):
            client.extract_pdf_text(
                uploaded,
                extra_body={"pages": "last-1"},
            )


@pytest.mark.asyncio
async def test_live_async_extract_pdf_text_invalid_pages(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
) -> None:
    resource = get_test_resource_path("report.pdf")
    async with AsyncPdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        uploaded = (await client.files.create_from_paths([resource]))[0]
        with pytest.raises(PdfRestApiError, match=r"(?i)page"):
            await client.extract_pdf_text(
                uploaded,
                extra_body={"pages": "last-1"},
            )
