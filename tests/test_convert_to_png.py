from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

import httpx
import pytest
from pydantic import ValidationError

from pdfrest import AsyncPdfRestClient, PdfRestClient
from pdfrest.models import PdfRestFile, PdfRestFileBasedResponse, PdfRestFileID
from pdfrest.models._internal import ConvertToGraphic

from .resources import get_test_resource_path

VALID_API_KEY = "12345678-1234-1234-1234-123456789abc"
ASYNC_API_KEY = "fedcba98-7654-3210-fedc-ba9876543210"


def _build_file_info_payload(file_id: str, name: str) -> dict[str, Any]:
    return {
        "id": file_id,
        "name": name,
        "url": f"https://api.pdfrest.com/resource/{file_id}",
        "type": "image/png",
        "size": 256,
        "modified": datetime(2024, 1, 1, tzinfo=timezone.utc)
        .isoformat()
        .replace("+00:00", "Z"),
        "scheduledDeletionTimeUtc": None,
    }


def _make_pdf_file(file_id: str, name: str = "example.pdf") -> PdfRestFile:
    return PdfRestFile.model_validate(
        {
            "id": file_id,
            "name": name,
            "url": f"https://api.pdfrest.com/resource/{file_id}",
            "type": "application/pdf",
            "size": 1024,
            "modified": datetime(2024, 1, 1, tzinfo=timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
            "scheduledDeletionTimeUtc": None,
        }
    )


def _assert_conversion_payload(
    payload: dict[str, Any], expected: dict[str, Any]
) -> None:
    for key, value in expected.items():
        assert payload[key] == value
    extras = set(payload) - set(expected)
    allowed_extras = {"color_model", "resolution"}
    assert extras <= allowed_extras
    if "resolution" not in expected:
        assert payload.get("resolution") == 300
    if "color_model" not in expected:
        assert payload.get("color_model") == "rgb"


def test_convert_to_png_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = _make_pdf_file(PdfRestFileID.generate(1))
    output_id = "1de305d2-b6a0-4b5d-9a55-4e4e6d8c2d39"

    request_payload = ConvertToGraphic.model_validate(
        {
            "files": [input_file],
            "output_prefix": "converted",
            "page_range": ["1", "2-3"],
            "resolution": 600,
            "color_model": "rgba",
            "smoothing": ["text", "image"],
        }
    ).model_dump(mode="json", by_alias=True)

    seen: dict[str, int] = {"post": 0, "get": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/png":
            seen["post"] += 1
            assert request.headers["wsn"] == "pdfrest-python"
            payload = json.loads(request.content.decode("utf-8"))
            _assert_conversion_payload(payload, request_payload)
            return httpx.Response(
                200,
                json={
                    "inputId": [input_file.id],
                    "outputId": [output_id],
                },
            )
        if request.method == "GET" and request.url.path == f"/resource/{output_id}":
            seen["get"] += 1
            assert request.url.params["format"] == "info"
            return httpx.Response(
                200, json=_build_file_info_payload(output_id, "converted-001.png")
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.convert_to_png(
            input_file,
            output_prefix="converted",
            page_range=["1", "2-3"],
            resolution=600,
            color_model="rgba",
            smoothing=["text", "image"],
        )

    assert seen == {"post": 1, "get": 1}
    assert isinstance(response, PdfRestFileBasedResponse)
    assert len(response.output_files) == 1
    output_file = response.output_files[0]
    assert output_file.name == "converted-001.png"
    assert output_file.name.startswith("converted")
    assert output_file.type == "image/png"
    assert output_file.size == 256
    assert str(output_file.url).endswith(output_id)
    assert str(response.input_id) == str(input_file.id)
    assert response.warning is None


def test_convert_to_png_request_customization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = _make_pdf_file(PdfRestFileID.generate(1))
    output_id = "9f4a9b10-3c55-4e6d-a111-1234567890ab"
    captured_timeout: dict[str, float | dict[str, float] | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/png":
            assert request.url.params["trace"] == "true"
            assert request.headers["X-Debug"] == "1"
            captured_timeout["value"] = request.extensions.get("timeout")
            payload = json.loads(request.content.decode("utf-8"))
            assert payload["debug"] is True
            assert payload["resolution"] == 450
            assert payload["id"] == str(input_file.id)
            return httpx.Response(
                200,
                json={
                    "inputId": [input_file.id],
                    "outputId": [output_id],
                },
            )
        if request.method == "GET" and request.url.path == f"/resource/{output_id}":
            assert request.url.params["format"] == "info"
            assert request.url.params["trace"] == "true"
            assert request.headers["X-Debug"] == "1"
            return httpx.Response(
                200, json=_build_file_info_payload(output_id, "custom-001.png")
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.convert_to_png(
            input_file,
            resolution=450,
            extra_query={"trace": "true"},
            extra_headers={"X-Debug": "1"},
            extra_body={"debug": True},
            timeout=0.25,
        )

    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.output_files[0].name == "custom-001.png"
    timeout_value = captured_timeout["value"]
    assert timeout_value is not None
    if isinstance(timeout_value, dict):
        assert all(
            component == pytest.approx(0.25) for component in timeout_value.values()
        )
    else:
        assert timeout_value == pytest.approx(0.25)


def test_convert_to_png_validation_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)

    def handler(_: httpx.Request) -> httpx.Response:
        pytest.fail("Request should not be sent when validation fails.")

    transport = httpx.MockTransport(handler)
    with (
        PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client,
        pytest.raises(ValidationError, match="greater than or equal to 12"),
    ):
        client.convert_to_png(
            _make_pdf_file(PdfRestFileID.generate(1)),
            resolution=5,
        )


@pytest.mark.asyncio
async def test_async_convert_to_png_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = _make_pdf_file(PdfRestFileID.generate(1))
    output_id = "2c134412-aaaa-4bbb-8ccc-dddddddddddd"

    request_payload = ConvertToGraphic.model_validate(
        {
            "files": [input_file],
            "output_prefix": "async-output",
            "page_range": "1-2",
            "resolution": 450,
            "color_model": "rgb",
            "smoothing": ["all"],
        }
    ).model_dump(mode="json", by_alias=True)

    seen: dict[str, int] = {"post": 0, "get": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/png":
            seen["post"] += 1
            payload = json.loads(request.content.decode("utf-8"))
            _assert_conversion_payload(payload, request_payload)
            return httpx.Response(
                200,
                json={
                    "inputId": [input_file.id],
                    "outputId": [output_id],
                },
            )
        if request.method == "GET" and request.url.path == f"/resource/{output_id}":
            seen["get"] += 1
            assert request.url.params["format"] == "info"
            return httpx.Response(
                200, json=_build_file_info_payload(output_id, "async-output-001.png")
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        response = await client.convert_to_png(
            [input_file],
            output_prefix="async-output",
            page_range="1-2",
            resolution=450,
            color_model="rgb",
            smoothing=["all"],
        )

    assert seen == {"post": 1, "get": 1}
    assert isinstance(response, PdfRestFileBasedResponse)
    output_file = response.output_files[0]
    assert output_file.name == "async-output-001.png"
    assert output_file.name.startswith("async-output")
    assert output_file.type == "image/png"
    assert output_file.size == 256
    assert str(output_file.url).endswith(output_id)
    assert str(response.input_id) == str(input_file.id)
    assert response.warning is None


@pytest.mark.asyncio
async def test_async_convert_to_png_request_customization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = _make_pdf_file(PdfRestFileID.generate(1))
    output_id = "abcdb5f9-1234-4c67-98ef-abcdefabcdef"
    captured_timeout: dict[str, float | dict[str, float] | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/png":
            assert request.url.params["trace"] == "true"
            assert request.headers["X-Debug"] == "async"
            captured_timeout["value"] = request.extensions.get("timeout")
            payload = json.loads(request.content.decode("utf-8"))
            assert payload["debug"] is True
            assert payload["resolution"] == 500
            assert payload["id"] == str(input_file.id)
            return httpx.Response(
                200,
                json={
                    "inputId": [input_file.id],
                    "outputId": [output_id],
                },
            )
        if request.method == "GET" and request.url.path == f"/resource/{output_id}":
            assert request.url.params["format"] == "info"
            assert request.url.params["trace"] == "true"
            assert request.headers["X-Debug"] == "async"
            return httpx.Response(
                200, json=_build_file_info_payload(output_id, "async-custom-001.png")
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        response = await client.convert_to_png(
            input_file,
            resolution=500,
            extra_query={"trace": "true"},
            extra_headers={"X-Debug": "async"},
            extra_body={"debug": True},
            timeout=0.6,
        )

    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.output_files[0].name == "async-custom-001.png"
    timeout_value = captured_timeout["value"]
    assert timeout_value is not None
    if isinstance(timeout_value, dict):
        assert all(
            component == pytest.approx(0.6) for component in timeout_value.values()
        )
    else:
        assert timeout_value == pytest.approx(0.6)


@pytest.mark.asyncio
async def test_async_convert_to_png_validation_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)

    def handler(_: httpx.Request) -> httpx.Response:
        pytest.fail("Request should not be sent when validation fails.")

    transport = httpx.MockTransport(handler)
    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        with pytest.raises(ValidationError, match="less than or equal to 2400"):
            await client.convert_to_png(
                _make_pdf_file(PdfRestFileID.generate(1)),
                resolution=9000,
            )


def test_convert_to_png_sequence_arguments(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = _make_pdf_file(PdfRestFileID.generate(1))
    output_id = "1f9c6d0a-5ec4-4f6c-b1f2-bbbbbbbbbbbb"

    request_payload = ConvertToGraphic.model_validate(
        {
            "files": [input_file],
            "page_range": "1, 3",
            "smoothing": "text",
        }
    ).model_dump(mode="json", by_alias=True, exclude_none=True, exclude_defaults=True)

    seen: dict[str, int] = {"post": 0, "get": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/png":
            seen["post"] += 1
            payload = json.loads(request.content.decode("utf-8"))
            _assert_conversion_payload(payload, request_payload)
            return httpx.Response(
                200,
                json={
                    "inputId": [input_file.id],
                    "outputId": [output_id],
                },
            )
        if request.method == "GET" and request.url.path == f"/resource/{output_id}":
            seen["get"] += 1
            return httpx.Response(
                200, json=_build_file_info_payload(output_id, "example-001.png")
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.convert_to_png(
            [input_file],
            page_range="1, 3",
            smoothing="text",
        )

    assert seen == {"post": 1, "get": 1}
    output_file = response.output_files[0]
    assert output_file.name == "example-001.png"
    assert output_file.name.startswith("example")
    assert output_file.type == "image/png"
    assert output_file.size == 256
    assert str(output_file.url).endswith(output_id)
    assert response.warning is None


def test_convert_to_png_page_range_variants(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = _make_pdf_file(PdfRestFileID.generate(1))
    output_id = "1c2d3e4f-5061-4728-b93a-aaaaaaaa2222"

    request_payload = ConvertToGraphic.model_validate(
        {
            "files": [input_file],
            "page_range": [1, "last", "6-last"],
        }
    ).model_dump(mode="json", by_alias=True, exclude_none=True, exclude_defaults=True)

    seen: dict[str, int] = {"post": 0, "get": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/png":
            seen["post"] += 1
            payload = json.loads(request.content.decode("utf-8"))
            _assert_conversion_payload(payload, request_payload)
            return httpx.Response(
                200,
                json={
                    "inputId": [input_file.id],
                    "outputId": [output_id],
                },
            )
        if request.method == "GET" and request.url.path == f"/resource/{output_id}":
            seen["get"] += 1
            return httpx.Response(
                200, json=_build_file_info_payload(output_id, "example-002.png")
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.convert_to_png(
            input_file,
            # Deliberately using an integer here to test automatic conversion.
            page_range=[1, "last", "6-last"],  # type: ignore[list-item]
        )

    assert seen == {"post": 1, "get": 1}
    output_file = response.output_files[0]
    assert output_file.name == "example-002.png"
    assert output_file.name.startswith("example")
    assert output_file.type == "image/png"
    assert output_file.size == 256
    assert str(output_file.url).endswith(output_id)


def test_convert_to_png_defaults_excluded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = _make_pdf_file(PdfRestFileID.generate(1))
    output_id = "2ab0c1d2-3e4f-4a5b-8c9d-dddddddddddd"

    request_payload = ConvertToGraphic.model_validate(
        {
            "files": input_file,
        }
    ).model_dump(mode="json", by_alias=True, exclude_none=True, exclude_defaults=True)

    seen: dict[str, int] = {"post": 0, "get": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/png":
            seen["post"] += 1
            payload = json.loads(request.content.decode("utf-8"))
            _assert_conversion_payload(payload, request_payload)
            return httpx.Response(
                200,
                json={
                    "inputId": [input_file.id],
                    "outputId": [output_id],
                },
            )
        if request.method == "GET" and request.url.path == f"/resource/{output_id}":
            seen["get"] += 1
            return httpx.Response(
                200, json=_build_file_info_payload(output_id, "example-001.png")
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.convert_to_png(input_file)

    assert seen == {"post": 1, "get": 1}
    output_file = response.output_files[0]
    assert output_file.name == "example-001.png"
    assert output_file.name.startswith("example")
    assert output_file.type == "image/png"
    assert output_file.size == 256
    assert str(output_file.url).endswith(output_id)
    assert response.warning is None


@pytest.mark.parametrize(
    ("bad_prefix", "expected"),
    [
        pytest.param(
            ".hidden",
            "The output prefix must not start with a `.`.",
            id="leading-dot",
        ),
        pytest.param(
            "profile.json",
            "The output prefix is a reserved name.",
            id="reserved-profile",
        ),
        pytest.param(
            "metadata.json",
            "The output prefix is a reserved name.",
            id="reserved-metadata",
        ),
        pytest.param(
            "invalid!name",
            "The output prefix must not contain special characters: '!'.",
            id="special-char",
        ),
        pytest.param(
            "nested/path",
            "The output prefix must not contain a directory separator.",
            id="directory-separator",
        ),
    ],
)
def test_convert_to_png_invalid_output_prefix(
    monkeypatch: pytest.MonkeyPatch, bad_prefix: str, expected: str
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)

    def handler(_: httpx.Request) -> httpx.Response:
        pytest.fail("Request should not be sent when validation fails.")

    transport = httpx.MockTransport(handler)
    with (
        PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client,
        pytest.raises(ValidationError, match=re.escape(expected)),
    ):
        client.convert_to_png(
            _make_pdf_file(PdfRestFileID.generate(1)),
            output_prefix=bad_prefix,
        )


@pytest.mark.parametrize(
    ("bad_page_range", "expected"),
    [
        pytest.param(
            "0",
            "Page numbers must be greater than or equal to 1.",
            id="scalar-zero",
        ),
        pytest.param(
            ["0"],
            "Page numbers must be greater than or equal to 1.",
            id="list-zero-string",
        ),
        pytest.param(
            [0],
            "Page numbers must be greater than or equal to 1.",
            id="list-zero-int",
        ),
        pytest.param(
            "last-5",
            "Page range start must be a page number greater than or equal to 1.",
            id="range-last-to-number",
        ),
        pytest.param(
            "3-2",
            "Page range end must be greater than or equal to the start.",
            id="range-descending",
        ),
        pytest.param(
            "foo",
            "Page range entries must be positive integers, 'last', or a range like '1-3' or '6-last'.",
            id="scalar-word",
        ),
        pytest.param(
            ["1", "foo"],
            "Page range entries must be positive integers, 'last', or a range like '1-3' or '6-last'.",
            id="list-mixed",
        ),
    ],
)
def test_convert_to_png_invalid_page_range_value(
    monkeypatch: pytest.MonkeyPatch, bad_page_range: Any, expected: str
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)

    def handler(_: httpx.Request) -> httpx.Response:
        pytest.fail("Request should not be sent when validation fails.")

    transport = httpx.MockTransport(handler)
    with (
        PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client,
        pytest.raises(ValidationError, match=re.escape(expected)),
    ):
        client.convert_to_png(
            _make_pdf_file(PdfRestFileID.generate(1)),
            page_range=bad_page_range,
        )


def test_convert_to_png_invalid_color_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)

    def handler(_: httpx.Request) -> httpx.Response:
        pytest.fail("Request should not be sent when validation fails.")

    transport = httpx.MockTransport(handler)
    with (
        PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client,
        pytest.raises(
            ValidationError,
            match=re.escape("Input should be 'rgb', 'rgba' or 'gray'"),
        ),
    ):
        client.convert_to_png(
            _make_pdf_file(PdfRestFileID.generate(1)),
            color_model="cmyk",  # type: ignore[arg-type]
        )


def test_convert_to_png_invalid_smoothing_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)

    def handler(_: httpx.Request) -> httpx.Response:
        pytest.fail("Request should not be sent when validation fails.")

    transport = httpx.MockTransport(handler)
    with (
        PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client,
        pytest.raises(
            ValidationError,
            match=re.escape("Input should be 'none', 'all', 'text', 'line' or 'image'"),
        ),
    ):
        client.convert_to_png(
            _make_pdf_file(PdfRestFileID.generate(1)),
            smoothing="invalid",  # type: ignore[arg-type]
        )


def test_convert_to_png_multiple_files_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)

    def handler(_: httpx.Request) -> httpx.Response:
        pytest.fail("Request should not be sent when validation fails.")

    first = _make_pdf_file(PdfRestFileID.generate(1))
    second = _make_pdf_file(PdfRestFileID.generate(1))
    transport = httpx.MockTransport(handler)
    with (
        PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client,
        pytest.raises(
            ValidationError,
            match=re.escape("List should have at most 1 item after validation"),
        ),
    ):
        client.convert_to_png([first, second])


def test_convert_to_png_empty_page_range_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)

    def handler(_: httpx.Request) -> httpx.Response:
        pytest.fail("Request should not be sent when validation fails.")

    transport = httpx.MockTransport(handler)
    with (
        PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client,
        pytest.raises(
            ValidationError,
            match=re.escape("List should have at least 1 item after validation"),
        ),
    ):
        client.convert_to_png(
            _make_pdf_file(PdfRestFileID.generate(1)),
            page_range=[],
        )


def test_live_convert_to_png(pdfrest_api_key: str, pdfrest_live_base_url: str) -> None:
    resource = get_test_resource_path("report.pdf")
    with PdfRestClient(
        api_key=pdfrest_api_key, base_url=pdfrest_live_base_url
    ) as client:
        uploaded = client.files.create_from_paths([resource])
        response = client.convert_to_png(
            uploaded[0],
            output_prefix="live-convert",
            page_range="1",
        )
    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.output_files


@pytest.mark.asyncio
async def test_live_async_convert_to_png(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
) -> None:
    resource = get_test_resource_path("report.pdf")
    async with AsyncPdfRestClient(
        api_key=pdfrest_api_key, base_url=pdfrest_live_base_url
    ) as client:
        uploaded = await client.files.create_from_paths([resource])
        response = await client.convert_to_png(
            uploaded[0],
            output_prefix="live-async-convert",
            page_range="1",
        )
    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.output_files
