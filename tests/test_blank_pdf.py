from __future__ import annotations

import json

import httpx
import pytest
from pydantic import ValidationError

from pdfrest import AsyncPdfRestClient, PdfRestClient
from pdfrest.models import PdfRestFileBasedResponse, PdfRestFileID
from pdfrest.models._internal import PdfBlankPayload

from .graphics_test_helpers import ASYNC_API_KEY, VALID_API_KEY, build_file_info_payload


@pytest.mark.parametrize(
    "page_size",
    [
        pytest.param("letter", id="letter"),
        pytest.param("legal", id="legal"),
        pytest.param("ledger", id="ledger"),
        pytest.param("A3", id="a3"),
        pytest.param("A4", id="a4"),
        pytest.param("A5", id="a5"),
    ],
)
@pytest.mark.parametrize(
    "page_orientation",
    [
        pytest.param("portrait", id="portrait"),
        pytest.param("landscape", id="landscape"),
    ],
)
def test_blank_pdf_standard_page_literals(
    monkeypatch: pytest.MonkeyPatch,
    page_size: str,
    page_orientation: str,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    output_id = str(PdfRestFileID.generate())

    payload_dump = PdfBlankPayload.model_validate(
        {
            "page_size": page_size,
            "page_count": 1,
            "page_orientation": page_orientation,
        }
    ).model_dump(mode="json", by_alias=True, exclude_none=True, exclude_unset=True)

    seen: dict[str, int] = {"post": 0, "get": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/blank-pdf":
            seen["post"] += 1
            payload = json.loads(request.content.decode("utf-8"))
            assert payload == payload_dump
            return httpx.Response(200, json={"outputId": [output_id]})
        if request.method == "GET" and request.url.path == f"/resource/{output_id}":
            seen["get"] += 1
            return httpx.Response(
                200,
                json=build_file_info_payload(
                    output_id,
                    "blank.pdf",
                    "application/pdf",
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.blank_pdf(
            page_size=page_size,
            page_count=1,
            page_orientation=page_orientation,
        )

    assert seen == {"post": 1, "get": 1}
    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.output_file.type == "application/pdf"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "page_size",
    [
        pytest.param("letter", id="letter"),
        pytest.param("legal", id="legal"),
        pytest.param("ledger", id="ledger"),
        pytest.param("A3", id="a3"),
        pytest.param("A4", id="a4"),
        pytest.param("A5", id="a5"),
    ],
)
@pytest.mark.parametrize(
    "page_orientation",
    [
        pytest.param("portrait", id="portrait"),
        pytest.param("landscape", id="landscape"),
    ],
)
async def test_async_blank_pdf_standard_page_literals(
    monkeypatch: pytest.MonkeyPatch,
    page_size: str,
    page_orientation: str,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    output_id = str(PdfRestFileID.generate())

    payload_dump = PdfBlankPayload.model_validate(
        {
            "page_size": page_size,
            "page_count": 1,
            "page_orientation": page_orientation,
        }
    ).model_dump(mode="json", by_alias=True, exclude_none=True, exclude_unset=True)

    seen: dict[str, int] = {"post": 0, "get": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/blank-pdf":
            seen["post"] += 1
            payload = json.loads(request.content.decode("utf-8"))
            assert payload == payload_dump
            return httpx.Response(200, json={"outputId": [output_id]})
        if request.method == "GET" and request.url.path == f"/resource/{output_id}":
            seen["get"] += 1
            return httpx.Response(
                200,
                json=build_file_info_payload(
                    output_id,
                    "blank.pdf",
                    "application/pdf",
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        response = await client.blank_pdf(
            page_size=page_size,
            page_count=1,
            page_orientation=page_orientation,
        )

    assert seen == {"post": 1, "get": 1}
    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.output_file.type == "application/pdf"


@pytest.mark.parametrize(
    "page_count",
    [
        pytest.param(1, id="min-page-count"),
        pytest.param(1000, id="max-page-count"),
    ],
)
def test_blank_pdf_page_count_boundaries_success(
    monkeypatch: pytest.MonkeyPatch,
    page_count: int,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    output_id = str(PdfRestFileID.generate())

    seen: dict[str, int] = {"post": 0, "get": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/blank-pdf":
            seen["post"] += 1
            payload = json.loads(request.content.decode("utf-8"))
            assert payload["page_count"] == page_count
            return httpx.Response(200, json={"outputId": [output_id]})
        if request.method == "GET" and request.url.path == f"/resource/{output_id}":
            seen["get"] += 1
            return httpx.Response(
                200,
                json=build_file_info_payload(
                    output_id,
                    "blank.pdf",
                    "application/pdf",
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.blank_pdf(
            page_size="letter",
            page_count=page_count,
            page_orientation="portrait",
        )

    assert isinstance(response, PdfRestFileBasedResponse)
    assert seen == {"post": 1, "get": 1}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "page_count",
    [
        pytest.param(1, id="min-page-count"),
        pytest.param(1000, id="max-page-count"),
    ],
)
async def test_async_blank_pdf_page_count_boundaries_success(
    monkeypatch: pytest.MonkeyPatch,
    page_count: int,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    output_id = str(PdfRestFileID.generate())

    seen: dict[str, int] = {"post": 0, "get": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/blank-pdf":
            seen["post"] += 1
            payload = json.loads(request.content.decode("utf-8"))
            assert payload["page_count"] == page_count
            return httpx.Response(200, json={"outputId": [output_id]})
        if request.method == "GET" and request.url.path == f"/resource/{output_id}":
            seen["get"] += 1
            return httpx.Response(
                200,
                json=build_file_info_payload(
                    output_id,
                    "blank.pdf",
                    "application/pdf",
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        response = await client.blank_pdf(
            page_size="letter",
            page_count=page_count,
            page_orientation="portrait",
        )

    assert isinstance(response, PdfRestFileBasedResponse)
    assert seen == {"post": 1, "get": 1}


@pytest.mark.parametrize(
    ("page_count", "match"),
    [
        pytest.param(0, "greater than or equal to 1", id="below-min"),
        pytest.param(1001, "less than or equal to 1000", id="above-max"),
    ],
)
def test_blank_pdf_page_count_boundaries_validation(
    monkeypatch: pytest.MonkeyPatch,
    page_count: int,
    match: str,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    transport = httpx.MockTransport(lambda request: (_ for _ in ()).throw(RuntimeError))

    with (
        PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client,
        pytest.raises(ValidationError, match=match),
    ):
        client.blank_pdf(
            page_size="A4",
            page_count=page_count,
            page_orientation="portrait",
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("page_count", "match"),
    [
        pytest.param(0, "greater than or equal to 1", id="below-min"),
        pytest.param(1001, "less than or equal to 1000", id="above-max"),
    ],
)
async def test_async_blank_pdf_page_count_boundaries_validation(
    monkeypatch: pytest.MonkeyPatch,
    page_count: int,
    match: str,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    transport = httpx.MockTransport(lambda request: (_ for _ in ()).throw(RuntimeError))

    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        with pytest.raises(ValidationError, match=match):
            await client.blank_pdf(
                page_size="A4",
                page_count=page_count,
                page_orientation="portrait",
            )


@pytest.mark.parametrize(
    ("custom_height", "custom_width", "match"),
    [
        pytest.param(0.0, 10.0, "greater than 0", id="height-zero"),
        pytest.param(-1.0, 10.0, "greater than 0", id="height-negative"),
        pytest.param(10.0, 0.0, "greater than 0", id="width-zero"),
        pytest.param(10.0, -1.0, "greater than 0", id="width-negative"),
    ],
)
def test_blank_pdf_custom_dimensions_validation(
    monkeypatch: pytest.MonkeyPatch,
    custom_height: float,
    custom_width: float,
    match: str,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    transport = httpx.MockTransport(lambda request: (_ for _ in ()).throw(RuntimeError))

    with (
        PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client,
        pytest.raises(ValidationError, match=match),
    ):
        client.blank_pdf(
            page_size="custom",
            page_count=1,
            custom_height=custom_height,
            custom_width=custom_width,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("custom_height", "custom_width", "match"),
    [
        pytest.param(0.0, 10.0, "greater than 0", id="height-zero"),
        pytest.param(-1.0, 10.0, "greater than 0", id="height-negative"),
        pytest.param(10.0, 0.0, "greater than 0", id="width-zero"),
        pytest.param(10.0, -1.0, "greater than 0", id="width-negative"),
    ],
)
async def test_async_blank_pdf_custom_dimensions_validation(
    monkeypatch: pytest.MonkeyPatch,
    custom_height: float,
    custom_width: float,
    match: str,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    transport = httpx.MockTransport(lambda request: (_ for _ in ()).throw(RuntimeError))

    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        with pytest.raises(ValidationError, match=match):
            await client.blank_pdf(
                page_size="custom",
                page_count=1,
                custom_height=custom_height,
                custom_width=custom_width,
            )


def test_blank_pdf_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    output_id = str(PdfRestFileID.generate())

    payload_dump = PdfBlankPayload.model_validate(
        {
            "page_size": "letter",
            "page_count": 2,
            "page_orientation": "portrait",
            "output": "blank",
        }
    ).model_dump(mode="json", by_alias=True, exclude_none=True, exclude_unset=True)

    seen: dict[str, int] = {"post": 0, "get": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/blank-pdf":
            seen["post"] += 1
            payload = json.loads(request.content.decode("utf-8"))
            assert payload == payload_dump
            return httpx.Response(
                200,
                json={
                    "outputId": [output_id],
                },
            )
        if request.method == "GET" and request.url.path == f"/resource/{output_id}":
            seen["get"] += 1
            assert request.url.params["format"] == "info"
            return httpx.Response(
                200,
                json=build_file_info_payload(
                    output_id,
                    "blank.pdf",
                    "application/pdf",
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.blank_pdf(
            page_size="letter",
            page_count=2,
            page_orientation="portrait",
            output="blank",
        )

    assert seen == {"post": 1, "get": 1}
    assert isinstance(response, PdfRestFileBasedResponse)
    output_file = response.output_file
    assert output_file.name == "blank.pdf"
    assert output_file.type == "application/pdf"
    assert response.warning is None
    assert response.input_ids == []
    with pytest.raises(ValueError, match=r"no input id was specified"):
        _ = response.input_id


def test_blank_pdf_request_customization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    output_id = str(PdfRestFileID.generate())
    captured_timeout: dict[str, float | dict[str, float] | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/blank-pdf":
            assert request.url.params["trace"] == "true"
            assert request.headers["X-Debug"] == "sync"
            captured_timeout["value"] = request.extensions.get("timeout")
            payload = json.loads(request.content.decode("utf-8"))
            assert payload["page_size"] == "custom"
            assert payload["custom_height"] == 792
            assert payload["custom_width"] == 612
            assert "page_orientation" not in payload
            assert payload["debug"] == "yes"
            assert payload["output"] == "custom"
            return httpx.Response(
                200,
                json={
                    "outputId": [output_id],
                },
            )
        if request.method == "GET" and request.url.path == f"/resource/{output_id}":
            assert request.url.params["format"] == "info"
            assert request.url.params["trace"] == "true"
            assert request.headers["X-Debug"] == "sync"
            return httpx.Response(
                200,
                json=build_file_info_payload(
                    output_id,
                    "custom.pdf",
                    "application/pdf",
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.blank_pdf(
            page_size="custom",
            page_count=3,
            custom_height=792,
            custom_width=612,
            output="custom",
            extra_query={"trace": "true"},
            extra_headers={"X-Debug": "sync"},
            extra_body={"debug": "yes"},
            timeout=0.29,
        )

    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.output_file.name == "custom.pdf"
    timeout_value = captured_timeout["value"]
    assert timeout_value is not None
    if isinstance(timeout_value, dict):
        assert all(
            component == pytest.approx(0.29) for component in timeout_value.values()
        )
    else:
        assert timeout_value == pytest.approx(0.29)


@pytest.mark.asyncio
async def test_async_blank_pdf_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    output_id = str(PdfRestFileID.generate())

    payload_dump = PdfBlankPayload.model_validate(
        {
            "page_size": "A4",
            "page_count": 1,
            "page_orientation": "landscape",
        }
    ).model_dump(mode="json", by_alias=True, exclude_none=True, exclude_unset=True)

    seen: dict[str, int] = {"post": 0, "get": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/blank-pdf":
            seen["post"] += 1
            payload = json.loads(request.content.decode("utf-8"))
            assert payload == payload_dump
            return httpx.Response(
                200,
                json={
                    "outputId": [output_id],
                },
            )
        if request.method == "GET" and request.url.path == f"/resource/{output_id}":
            seen["get"] += 1
            assert request.url.params["format"] == "info"
            return httpx.Response(
                200,
                json=build_file_info_payload(
                    output_id,
                    "async.pdf",
                    "application/pdf",
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        response = await client.blank_pdf(
            page_size="A4",
            page_count=1,
            page_orientation="landscape",
        )

    assert seen == {"post": 1, "get": 1}
    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.output_file.name == "async.pdf"
    assert response.output_file.type == "application/pdf"
    assert response.input_ids == []
    with pytest.raises(ValueError, match=r"no input id was specified"):
        _ = response.input_id


@pytest.mark.asyncio
async def test_async_blank_pdf_request_customization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    output_id = str(PdfRestFileID.generate())
    captured_timeout: dict[str, float | dict[str, float] | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/blank-pdf":
            assert request.url.params["trace"] == "async"
            assert request.headers["X-Debug"] == "async"
            captured_timeout["value"] = request.extensions.get("timeout")
            payload = json.loads(request.content.decode("utf-8"))
            assert payload["page_size"] == "custom"
            assert payload["custom_height"] == 100
            assert payload["custom_width"] == 50
            assert "page_orientation" not in payload
            assert payload["debug"] == "yes"
            return httpx.Response(
                200,
                json={
                    "outputId": [output_id],
                },
            )
        if request.method == "GET" and request.url.path == f"/resource/{output_id}":
            assert request.url.params["format"] == "info"
            assert request.url.params["trace"] == "async"
            assert request.headers["X-Debug"] == "async"
            return httpx.Response(
                200,
                json=build_file_info_payload(
                    output_id,
                    "async-custom.pdf",
                    "application/pdf",
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        response = await client.blank_pdf(
            page_size="custom",
            page_count=1,
            custom_height=100,
            custom_width=50,
            extra_query={"trace": "async"},
            extra_headers={"X-Debug": "async"},
            extra_body={"debug": "yes"},
            timeout=0.52,
        )

    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.output_file.name == "async-custom.pdf"
    timeout_value = captured_timeout["value"]
    assert timeout_value is not None
    if isinstance(timeout_value, dict):
        assert all(
            component == pytest.approx(0.52) for component in timeout_value.values()
        )
    else:
        assert timeout_value == pytest.approx(0.52)


def test_blank_pdf_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    transport = httpx.MockTransport(lambda request: (_ for _ in ()).throw(RuntimeError))

    with (
        PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client,
        pytest.raises(ValueError, match="page_orientation is required"),
    ):
        client.blank_pdf(page_size="letter", page_count=1)

    with (
        PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client,
        pytest.raises(ValueError, match="custom_height and custom_width are required"),
    ):
        client.blank_pdf(page_size="custom", page_count=1, custom_height=50)

    with (
        PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client,
        pytest.raises(
            ValueError, match="custom_height and custom_width can only be provided"
        ),
    ):
        client.blank_pdf(
            page_size="A3",
            page_count=1,
            page_orientation="portrait",
            custom_width=10,
        )

    with (
        PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client,
        pytest.raises(ValueError, match="page_orientation must be omitted"),
    ):
        client.blank_pdf(
            page_size="custom",
            page_count=1,
            page_orientation="portrait",
            custom_width=10,
            custom_height=10,
        )

    with (
        PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client,
        pytest.raises(
            ValidationError, match="Input should be less than or equal to 1000"
        ),
    ):
        client.blank_pdf(
            page_size="A4",
            page_count=1001,
            page_orientation="portrait",
        )
