from __future__ import annotations

import json
import re

import httpx
import pytest
from pydantic import ValidationError

from pdfrest import AsyncPdfRestClient, PdfRestClient
from pdfrest.models import PdfRestFile, PdfRestFileBasedResponse, PdfRestFileID
from pdfrest.models._internal import PdfImageWatermarkPayload, PdfTextWatermarkPayload

from .graphics_test_helpers import (
    ASYNC_API_KEY,
    VALID_API_KEY,
    build_file_info_payload,
    make_pdf_file,
)


def test_watermark_pdf_with_text(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(1))
    output_id = str(PdfRestFileID.generate())

    payload_dump = PdfTextWatermarkPayload.model_validate(
        {
            "files": [input_file],
            "watermark_text": "Confidential",
            "text_size": 72,
            "text_color": (255, 0, 0),
            "opacity": 0.5,
            "horizontal_alignment": "center",
            "vertical_alignment": "center",
            "x": 0,
            "y": 0,
            "rotation": 0,
            "pages": ["1", "3-5"],
            "behind_page": False,
            "output": "watermarked",
        }
    ).model_dump(mode="json", by_alias=True, exclude_none=True, exclude_unset=True)

    seen: dict[str, int] = {"post": 0, "get": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/watermarked-pdf":
            seen["post"] += 1
            payload = json.loads(request.content.decode("utf-8"))
            assert payload == payload_dump
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
                200,
                json=build_file_info_payload(
                    output_id,
                    "watermarked.pdf",
                    "application/pdf",
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.watermark_pdf_with_text(
            input_file,
            watermark_text="Confidential",
            text_color=(255, 0, 0),
            pages=["1", "3-5"],
            output="watermarked",
        )

    assert seen == {"post": 1, "get": 1}
    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.output_file.name == "watermarked.pdf"
    assert response.output_file.type == "application/pdf"
    assert str(response.input_id) == str(input_file.id)


def test_watermark_pdf_with_text_defaults_text_color_to_rgb_black(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(1))
    output_id = str(PdfRestFileID.generate())

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/watermarked-pdf":
            payload = json.loads(request.content.decode("utf-8"))
            assert payload["text_color_rgb"] == "0,0,0"
            assert "text_color_cmyk" not in payload
            return httpx.Response(
                200,
                json={
                    "inputId": [input_file.id],
                    "outputId": [output_id],
                },
            )
        if request.method == "GET" and request.url.path == f"/resource/{output_id}":
            assert request.url.params["format"] == "info"
            return httpx.Response(
                200,
                json=build_file_info_payload(
                    output_id,
                    "default-color.pdf",
                    "application/pdf",
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.watermark_pdf_with_text(
            input_file,
            watermark_text="DefaultColor",
        )

    assert response.output_file.name == "default-color.pdf"


def test_watermark_pdf_with_image(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(1))
    watermark_file = make_pdf_file(PdfRestFileID.generate(1), name="stamp.pdf")
    output_id = str(PdfRestFileID.generate())

    payload_dump = PdfImageWatermarkPayload.model_validate(
        {
            "files": [input_file],
            "watermark_file": [watermark_file],
            "watermark_file_scale": 0.8,
            "opacity": 0.5,
            "horizontal_alignment": "center",
            "vertical_alignment": "center",
            "x": 0,
            "behind_page": True,
            "rotation": 45,
            "y": 25,
        }
    ).model_dump(mode="json", by_alias=True, exclude_none=True, exclude_unset=True)

    seen: dict[str, int] = {"post": 0, "get": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/watermarked-pdf":
            seen["post"] += 1
            payload = json.loads(request.content.decode("utf-8"))
            assert payload == payload_dump
            assert payload["behind_page"] == "true"
            return httpx.Response(
                200,
                json={
                    "inputId": [input_file.id, watermark_file.id],
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
                    "stamped.pdf",
                    "application/pdf",
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.watermark_pdf_with_image(
            input_file,
            watermark_file=watermark_file,
            watermark_file_scale=0.8,
            behind_page=True,
            rotation=45,
            y=25,
        )

    assert seen == {"post": 1, "get": 1}
    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.output_file.name == "stamped.pdf"
    assert response.output_file.type == "application/pdf"
    assert response.warning is None
    assert [str(value) for value in response.input_ids] == [
        str(input_file.id),
        str(watermark_file.id),
    ]


def test_watermark_pdf_with_text_request_customization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(1))
    output_id = str(PdfRestFileID.generate())
    captured_timeout: dict[str, float | dict[str, float] | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/watermarked-pdf":
            assert request.url.params["trace"] == "true"
            assert request.headers["X-Debug"] == "sync"
            captured_timeout["value"] = request.extensions.get("timeout")
            payload = json.loads(request.content.decode("utf-8"))
            assert payload["watermark_text"] == "Draft"
            assert payload["text_color_cmyk"] == "0,0,0,50"
            assert payload["opacity"] == "0.25"
            assert payload["behind_page"] == "false"
            assert payload["output"] == "custom"
            assert payload["debug"] == "yes"
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
        response = client.watermark_pdf_with_text(
            input_file,
            watermark_text="Draft",
            text_color=(0, 0, 0, 50),
            opacity=0.25,
            output="custom",
            extra_query={"trace": "true"},
            extra_headers={"X-Debug": "sync"},
            extra_body={"debug": "yes"},
            timeout=0.31,
        )

    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.output_file.name == "custom.pdf"
    timeout_value = captured_timeout["value"]
    assert timeout_value is not None
    if isinstance(timeout_value, dict):
        assert all(
            component == pytest.approx(0.31) for component in timeout_value.values()
        )
    else:
        assert timeout_value == pytest.approx(0.31)


def test_watermark_pdf_with_image_request_customization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(1))
    watermark_file = make_pdf_file(PdfRestFileID.generate(1), name="custom-stamp.pdf")
    output_id = str(PdfRestFileID.generate())
    captured_timeout: dict[str, float | dict[str, float] | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/watermarked-pdf":
            assert request.url.params["trace"] == "true"
            assert request.headers["X-Debug"] == "sync-image"
            captured_timeout["value"] = request.extensions.get("timeout")
            payload = json.loads(request.content.decode("utf-8"))
            assert payload["id"] == str(input_file.id)
            assert payload["watermark_file_id"] == str(watermark_file.id)
            assert payload["watermark_file_scale"] == "0.75"
            assert payload["opacity"] == "0.2"
            assert payload["behind_page"] == "false"
            assert payload["output"] == "custom-image"
            assert payload["debug"] == "yes"
            return httpx.Response(
                200,
                json={
                    "inputId": [input_file.id, watermark_file.id],
                    "outputId": [output_id],
                },
            )
        if request.method == "GET" and request.url.path == f"/resource/{output_id}":
            assert request.url.params["format"] == "info"
            assert request.url.params["trace"] == "true"
            assert request.headers["X-Debug"] == "sync-image"
            return httpx.Response(
                200,
                json=build_file_info_payload(
                    output_id,
                    "custom-image.pdf",
                    "application/pdf",
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.watermark_pdf_with_image(
            input_file,
            watermark_file=watermark_file,
            watermark_file_scale=0.75,
            opacity=0.2,
            output="custom-image",
            extra_query={"trace": "true"},
            extra_headers={"X-Debug": "sync-image"},
            extra_body={"debug": "yes"},
            timeout=0.33,
        )

    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.output_file.name == "custom-image.pdf"
    timeout_value = captured_timeout["value"]
    assert timeout_value is not None
    if isinstance(timeout_value, dict):
        assert all(
            component == pytest.approx(0.33) for component in timeout_value.values()
        )
    else:
        assert timeout_value == pytest.approx(0.33)


def test_watermark_pdf_with_text_validation_rejects_invalid_text_color_channel_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(1))
    with (
        PdfRestClient(
            api_key=VALID_API_KEY,
            transport=httpx.MockTransport(
                lambda _: (_ for _ in ()).throw(RuntimeError("Should not be called"))
            ),
        ) as client,
        pytest.raises(
            ValidationError,
            match=re.escape(
                "text_color must include exactly 3 (RGB) or 4 (CMYK) values."
            ),
        ),
    ):
        client.watermark_pdf_with_text(
            input_file,
            watermark_text="Confidential",
            text_color=(0, 0),
        )


def test_watermark_pdf_with_text_validation_rejects_non_pdf(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    bad_file = PdfRestFile.model_validate(
        {
            "id": str(PdfRestFileID.generate()),
            "name": "image.png",
            "type": "image/png",
            "url": "https://example.com/image.png",
            "size": 12,
            "modified": "2024-01-01T00:00:00Z",
        }
    )
    with (
        PdfRestClient(
            api_key=VALID_API_KEY,
            transport=httpx.MockTransport(
                lambda _: (_ for _ in ()).throw(RuntimeError("Should not be called"))
            ),
        ) as client,
        pytest.raises(ValidationError, match="Must be a PDF file"),
    ):
        client.watermark_pdf_with_text(bad_file, watermark_text="Hi")


def test_watermark_pdf_with_image_validation_rejects_non_pdf_watermark(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(1))
    bad_watermark = PdfRestFile.model_validate(
        {
            "id": str(PdfRestFileID.generate()),
            "name": "overlay.png",
            "type": "image/png",
            "url": "https://example.com/overlay.png",
            "size": 12,
            "modified": "2024-01-01T00:00:00Z",
        }
    )
    with (
        PdfRestClient(
            api_key=VALID_API_KEY,
            transport=httpx.MockTransport(
                lambda _: (_ for _ in ()).throw(RuntimeError("Should not be called"))
            ),
        ) as client,
        pytest.raises(ValidationError, match="Must be a PDF file"),
    ):
        client.watermark_pdf_with_image(input_file, watermark_file=bad_watermark)


def test_watermark_pdf_with_text_validation_rejects_short_text_size(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(1))
    with (
        PdfRestClient(
            api_key=VALID_API_KEY,
            transport=httpx.MockTransport(
                lambda _: (_ for _ in ()).throw(RuntimeError("Should not be called"))
            ),
        ) as client,
        pytest.raises(
            ValidationError, match="Input should be greater than or equal to 5"
        ),
    ):
        client.watermark_pdf_with_text(input_file, watermark_text="Hi", text_size=4)


@pytest.mark.parametrize(
    ("text_size", "expected_text_size"),
    [
        pytest.param(5, "5", id="min"),
        pytest.param(100, "100", id="max"),
    ],
)
def test_watermark_pdf_with_text_text_size_boundary_values(
    monkeypatch: pytest.MonkeyPatch,
    text_size: int,
    expected_text_size: str,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(1))
    output_id = str(PdfRestFileID.generate())

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/watermarked-pdf":
            payload = json.loads(request.content.decode("utf-8"))
            assert payload["text_size"] == expected_text_size
            return httpx.Response(
                200,
                json={
                    "inputId": [input_file.id],
                    "outputId": [output_id],
                },
            )
        if request.method == "GET" and request.url.path == f"/resource/{output_id}":
            assert request.url.params["format"] == "info"
            return httpx.Response(
                200,
                json=build_file_info_payload(
                    output_id,
                    "text-size.pdf",
                    "application/pdf",
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    with PdfRestClient(
        api_key=VALID_API_KEY,
        transport=httpx.MockTransport(handler),
    ) as client:
        response = client.watermark_pdf_with_text(
            input_file,
            watermark_text="SizeBoundary",
            text_size=text_size,
        )

    assert response.output_file.name == "text-size.pdf"


@pytest.mark.parametrize(
    ("text_size", "match"),
    [
        pytest.param(4, "Input should be greater than or equal to 5", id="below-min"),
        pytest.param(101, "Input should be less than or equal to 100", id="above-max"),
    ],
)
def test_watermark_pdf_with_text_validation_rejects_out_of_range_text_size(
    monkeypatch: pytest.MonkeyPatch,
    text_size: int,
    match: str,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(1))
    with (
        PdfRestClient(
            api_key=VALID_API_KEY,
            transport=httpx.MockTransport(
                lambda _: (_ for _ in ()).throw(RuntimeError("Should not be called"))
            ),
        ) as client,
        pytest.raises(ValidationError, match=match),
    ):
        client.watermark_pdf_with_text(
            input_file,
            watermark_text="SizeBoundary",
            text_size=text_size,
        )


@pytest.mark.parametrize(
    ("opacity", "expected_opacity"),
    [
        pytest.param(0.0, "0.0", id="min"),
        pytest.param(1.0, "1.0", id="max"),
    ],
)
def test_watermark_pdf_with_text_opacity_boundary_values(
    monkeypatch: pytest.MonkeyPatch,
    opacity: float,
    expected_opacity: str,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(1))
    output_id = str(PdfRestFileID.generate())

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/watermarked-pdf":
            payload = json.loads(request.content.decode("utf-8"))
            assert payload["opacity"] == expected_opacity
            return httpx.Response(
                200,
                json={
                    "inputId": [input_file.id],
                    "outputId": [output_id],
                },
            )
        if request.method == "GET" and request.url.path == f"/resource/{output_id}":
            assert request.url.params["format"] == "info"
            return httpx.Response(
                200,
                json=build_file_info_payload(
                    output_id,
                    "opacity-text.pdf",
                    "application/pdf",
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    with PdfRestClient(
        api_key=VALID_API_KEY,
        transport=httpx.MockTransport(handler),
    ) as client:
        response = client.watermark_pdf_with_text(
            input_file,
            watermark_text="OpacityBoundary",
            opacity=opacity,
        )

    assert response.output_file.name == "opacity-text.pdf"


@pytest.mark.parametrize(
    ("opacity", "match"),
    [
        pytest.param(
            -0.01, "Input should be greater than or equal to 0", id="below-min"
        ),
        pytest.param(1.01, "Input should be less than or equal to 1", id="above-max"),
    ],
)
def test_watermark_pdf_with_text_validation_rejects_out_of_range_opacity(
    monkeypatch: pytest.MonkeyPatch,
    opacity: float,
    match: str,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(1))
    with (
        PdfRestClient(
            api_key=VALID_API_KEY,
            transport=httpx.MockTransport(
                lambda _: (_ for _ in ()).throw(RuntimeError("Should not be called"))
            ),
        ) as client,
        pytest.raises(ValidationError, match=match),
    ):
        client.watermark_pdf_with_text(
            input_file,
            watermark_text="OpacityBoundary",
            opacity=opacity,
        )


@pytest.mark.parametrize(
    ("watermark_file_scale", "expected_scale"),
    [
        pytest.param(0.0, "0.0", id="min"),
        pytest.param(0.01, "0.01", id="inside"),
    ],
)
def test_watermark_pdf_with_image_scale_boundary_values(
    monkeypatch: pytest.MonkeyPatch,
    watermark_file_scale: float,
    expected_scale: str,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(1))
    watermark_file = make_pdf_file(PdfRestFileID.generate(1), name="boundary-stamp.pdf")
    output_id = str(PdfRestFileID.generate())

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/watermarked-pdf":
            payload = json.loads(request.content.decode("utf-8"))
            assert payload["watermark_file_scale"] == expected_scale
            return httpx.Response(
                200,
                json={
                    "inputId": [input_file.id, watermark_file.id],
                    "outputId": [output_id],
                },
            )
        if request.method == "GET" and request.url.path == f"/resource/{output_id}":
            assert request.url.params["format"] == "info"
            return httpx.Response(
                200,
                json=build_file_info_payload(
                    output_id,
                    "scale-image.pdf",
                    "application/pdf",
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    with PdfRestClient(
        api_key=VALID_API_KEY,
        transport=httpx.MockTransport(handler),
    ) as client:
        response = client.watermark_pdf_with_image(
            input_file,
            watermark_file=watermark_file,
            watermark_file_scale=watermark_file_scale,
        )

    assert response.output_file.name == "scale-image.pdf"


def test_watermark_pdf_with_image_validation_rejects_negative_watermark_file_scale(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(1))
    watermark_file = make_pdf_file(PdfRestFileID.generate(1), name="boundary-stamp.pdf")
    with (
        PdfRestClient(
            api_key=VALID_API_KEY,
            transport=httpx.MockTransport(
                lambda _: (_ for _ in ()).throw(RuntimeError("Should not be called"))
            ),
        ) as client,
        pytest.raises(
            ValidationError, match="Input should be greater than or equal to 0"
        ),
    ):
        client.watermark_pdf_with_image(
            input_file,
            watermark_file=watermark_file,
            watermark_file_scale=-0.01,
        )


@pytest.mark.parametrize(
    ("text_size", "expected_text_size"),
    [
        pytest.param(5, "5", id="min"),
        pytest.param(100, "100", id="max"),
    ],
)
@pytest.mark.asyncio
async def test_async_watermark_pdf_with_text_text_size_boundary_values(
    monkeypatch: pytest.MonkeyPatch,
    text_size: int,
    expected_text_size: str,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(2))
    output_id = str(PdfRestFileID.generate())

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/watermarked-pdf":
            payload = json.loads(request.content.decode("utf-8"))
            assert payload["text_size"] == expected_text_size
            return httpx.Response(
                200,
                json={
                    "inputId": [input_file.id],
                    "outputId": [output_id],
                },
            )
        if request.method == "GET" and request.url.path == f"/resource/{output_id}":
            assert request.url.params["format"] == "info"
            return httpx.Response(
                200,
                json=build_file_info_payload(
                    output_id,
                    "async-text-size.pdf",
                    "application/pdf",
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    async with AsyncPdfRestClient(
        api_key=ASYNC_API_KEY,
        transport=httpx.MockTransport(handler),
    ) as client:
        response = await client.watermark_pdf_with_text(
            input_file,
            watermark_text="AsyncSizeBoundary",
            text_size=text_size,
        )

    assert response.output_file.name == "async-text-size.pdf"


@pytest.mark.parametrize(
    ("text_size", "match"),
    [
        pytest.param(4, "Input should be greater than or equal to 5", id="below-min"),
        pytest.param(101, "Input should be less than or equal to 100", id="above-max"),
    ],
)
@pytest.mark.asyncio
async def test_async_watermark_pdf_with_text_validation_rejects_out_of_range_text_size(
    monkeypatch: pytest.MonkeyPatch,
    text_size: int,
    match: str,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(2))
    transport = httpx.MockTransport(
        lambda _: (_ for _ in ()).throw(RuntimeError("Should not be called"))
    )
    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        with pytest.raises(ValidationError, match=match):
            await client.watermark_pdf_with_text(
                input_file,
                watermark_text="AsyncSizeBoundary",
                text_size=text_size,
            )


@pytest.mark.asyncio
async def test_async_watermark_pdf_with_text_validation_rejects_invalid_text_color_channel_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(2))
    transport = httpx.MockTransport(
        lambda _: (_ for _ in ()).throw(RuntimeError("Should not be called"))
    )
    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        with pytest.raises(
            ValidationError,
            match=re.escape(
                "text_color must include exactly 3 (RGB) or 4 (CMYK) values."
            ),
        ):
            await client.watermark_pdf_with_text(
                input_file,
                watermark_text="AsyncColorValidation",
                text_color=(0, 0),
            )


@pytest.mark.parametrize(
    ("opacity", "expected_opacity"),
    [
        pytest.param(0.0, "0.0", id="min"),
        pytest.param(1.0, "1.0", id="max"),
    ],
)
@pytest.mark.asyncio
async def test_async_watermark_pdf_with_text_opacity_boundary_values(
    monkeypatch: pytest.MonkeyPatch,
    opacity: float,
    expected_opacity: str,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(2))
    output_id = str(PdfRestFileID.generate())

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/watermarked-pdf":
            payload = json.loads(request.content.decode("utf-8"))
            assert payload["opacity"] == expected_opacity
            return httpx.Response(
                200,
                json={
                    "inputId": [input_file.id],
                    "outputId": [output_id],
                },
            )
        if request.method == "GET" and request.url.path == f"/resource/{output_id}":
            assert request.url.params["format"] == "info"
            return httpx.Response(
                200,
                json=build_file_info_payload(
                    output_id,
                    "async-opacity-text.pdf",
                    "application/pdf",
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    async with AsyncPdfRestClient(
        api_key=ASYNC_API_KEY,
        transport=httpx.MockTransport(handler),
    ) as client:
        response = await client.watermark_pdf_with_text(
            input_file,
            watermark_text="AsyncOpacityBoundary",
            opacity=opacity,
        )

    assert response.output_file.name == "async-opacity-text.pdf"


@pytest.mark.parametrize(
    ("opacity", "match"),
    [
        pytest.param(
            -0.01, "Input should be greater than or equal to 0", id="below-min"
        ),
        pytest.param(1.01, "Input should be less than or equal to 1", id="above-max"),
    ],
)
@pytest.mark.asyncio
async def test_async_watermark_pdf_with_text_validation_rejects_out_of_range_opacity(
    monkeypatch: pytest.MonkeyPatch,
    opacity: float,
    match: str,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(2))
    transport = httpx.MockTransport(
        lambda _: (_ for _ in ()).throw(RuntimeError("Should not be called"))
    )
    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        with pytest.raises(ValidationError, match=match):
            await client.watermark_pdf_with_text(
                input_file,
                watermark_text="AsyncOpacityBoundary",
                opacity=opacity,
            )


@pytest.mark.parametrize(
    ("watermark_file_scale", "expected_scale"),
    [
        pytest.param(0.0, "0.0", id="min"),
        pytest.param(0.01, "0.01", id="inside"),
    ],
)
@pytest.mark.asyncio
async def test_async_watermark_pdf_with_image_scale_boundary_values(
    monkeypatch: pytest.MonkeyPatch,
    watermark_file_scale: float,
    expected_scale: str,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(2))
    watermark_file = make_pdf_file(PdfRestFileID.generate(2), name="boundary-stamp.pdf")
    output_id = str(PdfRestFileID.generate())

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/watermarked-pdf":
            payload = json.loads(request.content.decode("utf-8"))
            assert payload["watermark_file_scale"] == expected_scale
            return httpx.Response(
                200,
                json={
                    "inputId": [input_file.id, watermark_file.id],
                    "outputId": [output_id],
                },
            )
        if request.method == "GET" and request.url.path == f"/resource/{output_id}":
            assert request.url.params["format"] == "info"
            return httpx.Response(
                200,
                json=build_file_info_payload(
                    output_id,
                    "async-scale-image.pdf",
                    "application/pdf",
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    async with AsyncPdfRestClient(
        api_key=ASYNC_API_KEY,
        transport=httpx.MockTransport(handler),
    ) as client:
        response = await client.watermark_pdf_with_image(
            input_file,
            watermark_file=watermark_file,
            watermark_file_scale=watermark_file_scale,
        )

    assert response.output_file.name == "async-scale-image.pdf"


@pytest.mark.asyncio
async def test_async_watermark_pdf_with_image_validation_rejects_negative_watermark_file_scale(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(2))
    watermark_file = make_pdf_file(PdfRestFileID.generate(2), name="boundary-stamp.pdf")
    transport = httpx.MockTransport(
        lambda _: (_ for _ in ()).throw(RuntimeError("Should not be called"))
    )
    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        with pytest.raises(
            ValidationError, match="Input should be greater than or equal to 0"
        ):
            await client.watermark_pdf_with_image(
                input_file,
                watermark_file=watermark_file,
                watermark_file_scale=-0.01,
            )


@pytest.mark.asyncio
async def test_async_watermark_pdf_with_text(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(2))
    output_id = str(PdfRestFileID.generate())

    payload_dump = PdfTextWatermarkPayload.model_validate(
        {
            "files": [input_file],
            "watermark_text": "Async",
            "text_size": 72,
            "text_color": (0, 0, 0),
            "opacity": 0.6,
            "horizontal_alignment": "center",
            "vertical_alignment": "center",
            "x": 0,
            "y": 0,
            "rotation": 0,
            "behind_page": False,
        }
    ).model_dump(mode="json", by_alias=True, exclude_none=True, exclude_unset=True)

    seen: dict[str, int] = {"post": 0, "get": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/watermarked-pdf":
            seen["post"] += 1
            payload = json.loads(request.content.decode("utf-8"))
            assert payload == payload_dump
            assert payload["behind_page"] == "false"
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
                200,
                json=build_file_info_payload(
                    output_id,
                    "async-watermarked.pdf",
                    "application/pdf",
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        response = await client.watermark_pdf_with_text(
            input_file,
            watermark_text="Async",
            opacity=0.6,
        )

    assert seen == {"post": 1, "get": 1}
    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.output_file.name == "async-watermarked.pdf"
    assert response.output_file.type == "application/pdf"
    assert str(response.input_id) == str(input_file.id)


@pytest.mark.asyncio
async def test_async_watermark_pdf_with_image(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(2))
    watermark_file = make_pdf_file(PdfRestFileID.generate(2), name="async-stamp.pdf")
    output_id = str(PdfRestFileID.generate())

    payload_dump = PdfImageWatermarkPayload.model_validate(
        {
            "files": [input_file],
            "watermark_file": [watermark_file],
            "watermark_file_scale": 0.5,
            "opacity": 0.2,
            "horizontal_alignment": "center",
            "vertical_alignment": "center",
            "x": 0,
            "y": 0,
            "rotation": 0,
            "pages": ["2-last"],
            "behind_page": False,
        }
    ).model_dump(mode="json", by_alias=True, exclude_none=True, exclude_unset=True)

    seen: dict[str, int] = {"post": 0, "get": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/watermarked-pdf":
            seen["post"] += 1
            payload = json.loads(request.content.decode("utf-8"))
            assert payload == payload_dump
            assert payload["behind_page"] == "false"
            return httpx.Response(
                200,
                json={
                    "inputId": [input_file.id, watermark_file.id],
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
                    "async-stamped.pdf",
                    "application/pdf",
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        response = await client.watermark_pdf_with_image(
            input_file,
            watermark_file=watermark_file,
            opacity=0.2,
            pages=["2-last"],
        )

    assert seen == {"post": 1, "get": 1}
    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.output_file.name == "async-stamped.pdf"
    assert response.output_file.type == "application/pdf"
    assert [str(value) for value in response.input_ids] == [
        str(input_file.id),
        str(watermark_file.id),
    ]


@pytest.mark.asyncio
async def test_async_watermark_pdf_with_text_request_customization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(2))
    output_id = str(PdfRestFileID.generate())
    captured_timeout: dict[str, float | dict[str, float] | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/watermarked-pdf":
            assert request.url.params["trace"] == "async"
            assert request.headers["X-Debug"] == "async"
            captured_timeout["value"] = request.extensions.get("timeout")
            payload = json.loads(request.content.decode("utf-8"))
            assert payload["watermark_text"] == "AsyncDraft"
            assert payload["text_color_rgb"] == "12,34,56"
            assert payload["horizontal_alignment"] == "left"
            assert payload["vertical_alignment"] == "bottom"
            assert payload["x"] == "-72"
            assert payload["y"] == "144"
            assert payload["rotation"] == "30"
            assert payload["behind_page"] == "false"
            return httpx.Response(
                200,
                json={
                    "inputId": [input_file.id],
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
        response = await client.watermark_pdf_with_text(
            input_file,
            watermark_text="AsyncDraft",
            text_color=(12, 34, 56),
            horizontal_alignment="left",
            vertical_alignment="bottom",
            x=-72,
            y=144,
            rotation=30,
            extra_query={"trace": "async"},
            extra_headers={"X-Debug": "async"},
            extra_body={"debug": "async"},
            timeout=0.42,
        )

    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.output_file.name == "async-custom.pdf"
    timeout_value = captured_timeout["value"]
    assert timeout_value is not None
    if isinstance(timeout_value, dict):
        assert all(
            component == pytest.approx(0.42) for component in timeout_value.values()
        )
    else:
        assert timeout_value == pytest.approx(0.42)


@pytest.mark.asyncio
async def test_async_watermark_pdf_with_image_request_customization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(2))
    watermark_file = make_pdf_file(
        PdfRestFileID.generate(2), name="async-custom-stamp.pdf"
    )
    output_id = str(PdfRestFileID.generate())
    captured_timeout: dict[str, float | dict[str, float] | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/watermarked-pdf":
            assert request.url.params["trace"] == "async"
            assert request.headers["X-Debug"] == "async-image"
            captured_timeout["value"] = request.extensions.get("timeout")
            payload = json.loads(request.content.decode("utf-8"))
            assert payload["id"] == str(input_file.id)
            assert payload["watermark_file_id"] == str(watermark_file.id)
            assert payload["watermark_file_scale"] == "0.6"
            assert payload["opacity"] == "0.25"
            assert payload["behind_page"] == "false"
            assert payload["output"] == "async-custom-image"
            assert payload["debug"] == "async"
            return httpx.Response(
                200,
                json={
                    "inputId": [input_file.id, watermark_file.id],
                    "outputId": [output_id],
                },
            )
        if request.method == "GET" and request.url.path == f"/resource/{output_id}":
            assert request.url.params["format"] == "info"
            assert request.url.params["trace"] == "async"
            assert request.headers["X-Debug"] == "async-image"
            return httpx.Response(
                200,
                json=build_file_info_payload(
                    output_id,
                    "async-custom-image.pdf",
                    "application/pdf",
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        response = await client.watermark_pdf_with_image(
            input_file,
            watermark_file=watermark_file,
            watermark_file_scale=0.6,
            opacity=0.25,
            output="async-custom-image",
            extra_query={"trace": "async"},
            extra_headers={"X-Debug": "async-image"},
            extra_body={"debug": "async"},
            timeout=0.52,
        )

    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.output_file.name == "async-custom-image.pdf"
    timeout_value = captured_timeout["value"]
    assert timeout_value is not None
    if isinstance(timeout_value, dict):
        assert all(
            component == pytest.approx(0.52) for component in timeout_value.values()
        )
    else:
        assert timeout_value == pytest.approx(0.52)
