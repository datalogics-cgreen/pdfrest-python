from __future__ import annotations

import json
import logging
from collections.abc import Sequence

import httpx
import pytest
from pydantic import ValidationError

from pdfrest import AsyncPdfRestClient, PdfRestClient
from pdfrest.models import PdfRestFileID, PdfRestInfoResponse
from pdfrest.types import ALL_PDF_INFO_QUERIES, PdfInfoQuery

from .graphics_test_helpers import ASYNC_API_KEY, VALID_API_KEY, make_pdf_file


@pytest.mark.parametrize(
    ("queries_input", "expected_serialized"),
    [
        pytest.param(["tagged", "page_count"], "tagged,page_count", id="list"),
        pytest.param(("tagged", "page_count"), "tagged,page_count", id="tuple"),
        pytest.param("tagged", "tagged", id="single"),
    ],
)
def test_query_pdf_info_success(
    monkeypatch: pytest.MonkeyPatch,
    queries_input: Sequence[PdfInfoQuery] | PdfInfoQuery,
    expected_serialized: str,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(str(PdfRestFileID.generate()))

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method != "POST" or request.url.path != "/pdf-info":
            msg = f"Unexpected request {request.method} {request.url}"
            raise AssertionError(msg)
        payload = json.loads(request.content.decode("utf-8"))
        assert payload == {
            "id": str(input_file.id),
            "queries": expected_serialized,
        }
        return httpx.Response(
            200,
            json={
                "inputId": str(input_file.id),
                "page_count": 2,
                "title": "Example Document",
                "tagged": True,
                "allQueriesProcessed": True,
            },
        )

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.query_pdf_info(input_file, queries=queries_input)

    assert isinstance(response, PdfRestInfoResponse)
    assert response.page_count == 2
    assert response.title == "Example Document"
    assert response.tagged is True
    assert response.all_queries_processed is True


def test_query_pdf_info_default_queries(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(str(PdfRestFileID.generate()))
    expected_serialized = ",".join(ALL_PDF_INFO_QUERIES)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method != "POST" or request.url.path != "/pdf-info":
            msg = f"Unexpected request {request.method} {request.url}"
            raise AssertionError(msg)
        payload = json.loads(request.content.decode("utf-8"))
        assert payload == {
            "id": str(input_file.id),
            "queries": expected_serialized,
        }
        return httpx.Response(
            200,
            json={
                "inputId": str(input_file.id),
                "page_count": 1,
                "tagged": False,
                "allQueriesProcessed": True,
            },
        )

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.query_pdf_info(input_file)

    assert isinstance(response, PdfRestInfoResponse)
    assert response.page_count == 1
    assert response.tagged is False


def test_query_pdf_info_request_customization(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    resource_id = PdfRestFileID.generate()
    resource_file = make_pdf_file(str(resource_id))
    captured_timeout: dict[str, float | dict[str, float] | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method != "POST" or request.url.path != "/pdf-info":
            msg = f"Unexpected request {request.method} {request.url}"
            raise AssertionError(msg)
        assert request.url.params["trace"] == "true"
        assert request.headers["X-Debug"] == "1"
        captured_timeout["value"] = request.extensions.get("timeout")
        payload = json.loads(request.content.decode("utf-8"))
        assert payload == {
            "id": str(resource_file.id),
            "queries": "tagged",
            "debug": True,
        }
        return httpx.Response(
            200,
            json={
                "inputId": str(resource_file.id),
                "tagged": False,
                "allQueriesProcessed": True,
            },
        )

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.query_pdf_info(
            resource_file,
            queries="tagged",
            extra_query={"trace": "true"},
            extra_headers={"X-Debug": "1"},
            extra_body={"debug": True},
            timeout=0.75,
        )

    assert isinstance(response, PdfRestInfoResponse)
    assert response.tagged is False
    timeout_value = captured_timeout["value"]
    assert timeout_value is not None
    if isinstance(timeout_value, dict):
        assert all(
            component == pytest.approx(0.75) for component in timeout_value.values()
        )
    else:
        assert timeout_value == pytest.approx(0.75)


def test_query_pdf_info_requires_queries(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(str(PdfRestFileID.generate()))
    transport = httpx.MockTransport(
        lambda request: pytest.fail("request should not be sent")
    )
    with (
        PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client,
        pytest.raises(ValidationError, match="List should have at least 1 item"),
    ):
        client.query_pdf_info(input_file, queries=[])


def test_query_pdf_info_rejects_invalid_queries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(str(PdfRestFileID.generate()))
    transport = httpx.MockTransport(
        lambda request: pytest.fail("request should not be sent")
    )
    with (
        PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client,
        pytest.raises(
            ValidationError,
            match="Input should be 'tagged'",
        ),
    ):
        client.query_pdf_info(input_file, queries=["not_a_real_query"])  # type: ignore[list-item]


def test_query_pdf_info_accepts_sequence(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    file_a = make_pdf_file(str(PdfRestFileID.generate()))

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method != "POST" or request.url.path != "/pdf-info":
            msg = f"Unexpected request {request.method} {request.url}"
            raise AssertionError(msg)
        payload = json.loads(request.content.decode("utf-8"))
        assert payload == {
            "id": str(file_a.id),
            "queries": "tagged,page_count",
        }
        return httpx.Response(
            200,
            json={
                "inputId": str(file_a.id),
                "tagged": True,
                "page_count": 5,
                "allQueriesProcessed": True,
            },
        )

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.query_pdf_info([file_a], queries=("tagged", "page_count"))

    assert isinstance(response, PdfRestInfoResponse)
    assert response.page_count == 5
    assert response.tagged is True


@pytest.mark.asyncio
async def test_async_query_pdf_info(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(str(PdfRestFileID.generate()))

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method != "POST" or request.url.path != "/pdf-info":
            msg = f"Unexpected request {request.method} {request.url}"
            raise AssertionError(msg)
        payload = json.loads(request.content.decode("utf-8"))
        assert payload == {
            "id": str(input_file.id),
            "queries": "tagged",
        }
        return httpx.Response(
            200,
            json={
                "inputId": str(input_file.id),
                "tagged": True,
                "allQueriesProcessed": True,
            },
        )

    transport = httpx.MockTransport(handler)
    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        response = await client.query_pdf_info(input_file, queries="tagged")

    assert isinstance(response, PdfRestInfoResponse)
    assert response.tagged is True
    assert response.all_queries_processed is True


def test_query_pdf_info_demo_redacted_booleans_replaced(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    caplog.set_level(logging.WARNING, logger="pdfrest.models")
    input_file = make_pdf_file(str(PdfRestFileID.generate()))

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method != "POST" or request.url.path != "/pdf-info":
            msg = f"Unexpected request {request.method} {request.url}"
            raise AssertionError(msg)
        return httpx.Response(
            200,
            json={
                "inputId": str(input_file.id),
                "tagged": "fa***",
                "image_only": "fa***",
                "contains_annotations": "fa***",
                "contains_signature": "fa***",
                "file_size": "25***",
                "restrict_permissions_set": "fa***",
                "contains_xfa": "fa***",
                "contains_acroforms": "fa***",
                "contains_javascript": "fa***",
                "contains_transparency": "fa***",
                "contains_embedded_file": "fa***",
                "uses_embedded_fonts": "fa***",
                "uses_nonembedded_fonts": "fa***",
                "pdfa": "fa***",
                "pdfua_claim": "fa***",
                "pdfe_claim": "fa***",
                "pdfx_claim": "fa***",
                "requires_password_to_open": "fa***",
                "allQueriesProcessed": "tr**",
            },
        )

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.query_pdf_info(
            input_file,
            queries=ALL_PDF_INFO_QUERIES,
        )

    assert response.tagged is False
    assert response.image_only is False
    assert response.contains_annotations is False
    assert response.contains_signature is False
    assert response.file_size == 0
    assert response.restrict_permissions_set is False
    assert response.contains_xfa is False
    assert response.contains_acroforms is False
    assert response.contains_javascript is False
    assert response.contains_transparency is False
    assert response.contains_embedded_file is False
    assert response.uses_embedded_fonts is False
    assert response.uses_nonembedded_fonts is False
    assert response.pdfa is False
    assert response.pdfua_claim is False
    assert response.pdfe_claim is False
    assert response.pdfx_claim is False
    assert response.requires_password_to_open is False
    assert response.all_queries_processed is True
    assert "Demo value fa*** detected in tagged; replaced with False" in caplog.text
    assert "Demo value 25*** detected in file_size; replaced with 0" in caplog.text
    assert "Demo value fa*** detected in pdfe_claim; replaced with False" in caplog.text
    assert "Demo value fa*** detected in pdfx_claim; replaced with False" in caplog.text
    assert (
        "Demo value fa*** detected in requires_password_to_open; replaced with False"
        in caplog.text
    )
    assert (
        "Demo value tr** detected in all_queries_processed; replaced with True"
        in caplog.text
    )
