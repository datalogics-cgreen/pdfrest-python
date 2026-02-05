from __future__ import annotations

from typing import Any, cast, get_args

import pytest

from pdfrest import AsyncPdfRestClient, PdfRestApiError, PdfRestClient
from pdfrest.models import PdfRestFile, PdfRestInfoResponse
from pdfrest.models._internal import PdfInfoPayload
from pdfrest.types import ALL_PDF_INFO_QUERIES, PdfInfoQuery

from ..resources import get_test_resource_path


def _allowed_queries() -> tuple[PdfInfoQuery, ...]:
    field = PdfInfoPayload.model_fields["queries"]
    (item_type,) = get_args(field.annotation)
    return cast(tuple[PdfInfoQuery, ...], tuple(get_args(item_type)))


ALLOWED_QUERIES: tuple[PdfInfoQuery, ...] = _allowed_queries()
assert ALLOWED_QUERIES == ALL_PDF_INFO_QUERIES


EXPECTED_VALUES: dict[PdfInfoQuery, Any] = {
    "tagged": False,
    "image_only": False,
    "title": "",
    "subject": "",
    "author": "",
    "producer": "",
    "creator": "",
    "creation_date": "",
    "modified_date": "",
    "keywords": "",
    "custom_metadata": {},
    "doc_language": "en-US",
    "page_count": 1,
    "contains_annotations": False,
    "contains_signature": False,
    "pdf_version": "1.7.0",
    "file_size": 25588,
    "filename": "report.pdf",
    "restrict_permissions_set": False,
    "contains_xfa": False,
    "contains_acroforms": False,
    "contains_javascript": False,
    "contains_transparency": False,
    "contains_embedded_file": False,
    "uses_embedded_fonts": False,
    "uses_nonembedded_fonts": False,
    "pdfa": False,
    "pdfua_claim": False,
    "pdfe_claim": False,
    "pdfx_claim": False,
    "requires_password_to_open": False,
}


def _assert_expected_value(query: PdfInfoQuery, value: Any) -> None:
    assert value == EXPECTED_VALUES[query]


@pytest.fixture(scope="module")
def uploaded_pdf(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
) -> PdfRestFile:
    resource = get_test_resource_path("report.pdf")
    with PdfRestClient(
        api_key=pdfrest_api_key, base_url=pdfrest_live_base_url
    ) as client:
        return client.files.create_from_paths([resource])[0]


@pytest.mark.parametrize("query_name", ALLOWED_QUERIES, ids=list(ALLOWED_QUERIES))
def test_live_pdf_info_queries(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf: PdfRestFile,
    query_name: PdfInfoQuery,
) -> None:
    with PdfRestClient(
        api_key=pdfrest_api_key, base_url=pdfrest_live_base_url
    ) as client:
        response = client.query_pdf_info(uploaded_pdf, queries=query_name)

    assert isinstance(response, PdfRestInfoResponse)
    assert str(response.input_id) == str(uploaded_pdf.id)
    assert response.all_queries_processed is True

    value = getattr(response, query_name)
    _assert_expected_value(query_name, value)


@pytest.mark.asyncio
@pytest.mark.parametrize("query_name", ALLOWED_QUERIES, ids=list(ALLOWED_QUERIES))
async def test_live_async_pdf_info_queries(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf: PdfRestFile,
    query_name: PdfInfoQuery,
) -> None:
    async with AsyncPdfRestClient(
        api_key=pdfrest_api_key, base_url=pdfrest_live_base_url
    ) as client:
        response = await client.query_pdf_info(uploaded_pdf, queries=query_name)

    assert isinstance(response, PdfRestInfoResponse)
    assert str(response.input_id) == str(uploaded_pdf.id)
    assert response.all_queries_processed is True

    value = getattr(response, query_name)
    _assert_expected_value(query_name, value)


@pytest.mark.parametrize(
    "invalid_query",
    [
        pytest.param("invalid_query", id="invalid-query"),
        pytest.param("tagged,!!invalid!!", id="mixed-invalid"),
        pytest.param("🚫", id="emoji"),
    ],
)
def test_live_pdf_info_invalid_query(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf: PdfRestFile,
    invalid_query: str,
) -> None:
    with (
        PdfRestClient(
            api_key=pdfrest_api_key, base_url=pdfrest_live_base_url
        ) as client,
        pytest.raises(PdfRestApiError, match=r"(?i)quer"),
    ):
        client.query_pdf_info(
            uploaded_pdf,
            queries="tagged",
            extra_body={"queries": invalid_query},
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "invalid_query",
    [
        pytest.param("invalid_query", id="invalid-query"),
        pytest.param("tagged,!!invalid!!", id="mixed-invalid"),
        pytest.param("🚫", id="emoji"),
    ],
)
async def test_live_async_pdf_info_invalid_query(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf: PdfRestFile,
    invalid_query: str,
) -> None:
    async with AsyncPdfRestClient(
        api_key=pdfrest_api_key, base_url=pdfrest_live_base_url
    ) as client:
        with pytest.raises(PdfRestApiError, match=r"(?i)quer"):
            await client.query_pdf_info(
                uploaded_pdf,
                queries="tagged",
                extra_body={"queries": invalid_query},
            )


@pytest.mark.parametrize(
    "query_group",
    [
        pytest.param(("tagged", "filename"), id="two-values"),
        pytest.param(("page_count", "file_size", "pdf_version"), id="three-values"),
    ],
)
def test_live_pdf_info_multiple_queries(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf: PdfRestFile,
    query_group: tuple[PdfInfoQuery, ...],
) -> None:
    with PdfRestClient(
        api_key=pdfrest_api_key, base_url=pdfrest_live_base_url
    ) as client:
        response = client.query_pdf_info(uploaded_pdf, queries=query_group)

    assert isinstance(response, PdfRestInfoResponse)
    assert str(response.input_id) == str(uploaded_pdf.id)
    assert response.all_queries_processed is True
    for item in query_group:
        _assert_expected_value(item, getattr(response, item))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "query_group",
    [
        pytest.param(("tagged", "filename"), id="two-values"),
        pytest.param(("page_count", "file_size", "pdf_version"), id="three-values"),
    ],
)
async def test_live_async_pdf_info_multiple_queries(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf: PdfRestFile,
    query_group: tuple[PdfInfoQuery, ...],
) -> None:
    async with AsyncPdfRestClient(
        api_key=pdfrest_api_key, base_url=pdfrest_live_base_url
    ) as client:
        response = await client.query_pdf_info(uploaded_pdf, queries=query_group)

    assert isinstance(response, PdfRestInfoResponse)
    assert str(response.input_id) == str(uploaded_pdf.id)
    assert response.all_queries_processed is True
    for item in query_group:
        _assert_expected_value(item, getattr(response, item))


def test_live_pdf_info_all_queries(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf: PdfRestFile,
) -> None:
    with PdfRestClient(
        api_key=pdfrest_api_key, base_url=pdfrest_live_base_url
    ) as client:
        response = client.query_pdf_info(uploaded_pdf, queries=ALLOWED_QUERIES)

    assert isinstance(response, PdfRestInfoResponse)
    assert str(response.input_id) == str(uploaded_pdf.id)
    assert response.all_queries_processed is True
    for query in ALLOWED_QUERIES:
        _assert_expected_value(query, getattr(response, query))


@pytest.mark.asyncio
async def test_live_async_pdf_info_all_queries(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf: PdfRestFile,
) -> None:
    async with AsyncPdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        response = await client.query_pdf_info(uploaded_pdf, queries=ALLOWED_QUERIES)

    assert isinstance(response, PdfRestInfoResponse)
    assert str(response.input_id) == str(uploaded_pdf.id)
    assert response.all_queries_processed is True
    for query in ALLOWED_QUERIES:
        _assert_expected_value(query, getattr(response, query))
