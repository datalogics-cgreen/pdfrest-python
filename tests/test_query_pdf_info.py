from __future__ import annotations

import json
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
