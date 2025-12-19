from __future__ import annotations

import json

import httpx
import pytest
from pydantic import ValidationError

from pdfrest import AsyncPdfRestClient, PdfRestClient
from pdfrest.models import PdfRestFile, PdfRestFileBasedResponse, PdfRestFileID
from pdfrest.models._internal import PdfCompressPayload

from .graphics_test_helpers import (
    ASYNC_API_KEY,
    VALID_API_KEY,
    build_file_info_payload,
    make_pdf_file,
)


def make_profile_file(file_id: str) -> PdfRestFile:
    return PdfRestFile.model_validate(
        build_file_info_payload(file_id, "profile.json", "application/json")
    )


def test_compress_pdf_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(1))
    output_id = str(PdfRestFileID.generate())

    payload_dump = PdfCompressPayload.model_validate(
        {"files": [input_file], "compression_level": "low"}
    ).model_dump(mode="json", by_alias=True, exclude_none=True, exclude_unset=True)

    seen: dict[str, int] = {"post": 0, "get": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/compressed-pdf":
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
                    "compressed.pdf",
                    "application/pdf",
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.compress_pdf(input_file, compression_level="low")

    assert seen == {"post": 1, "get": 1}
    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.output_file.name == "compressed.pdf"
    assert str(response.input_id) == str(input_file.id)


def test_compress_pdf_custom_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(1))
    profile_file = make_profile_file(str(PdfRestFileID.generate()))
    output_id = str(PdfRestFileID.generate())

    payload_dump = PdfCompressPayload.model_validate(
        {
            "files": [input_file],
            "compression_level": "custom",
            "profile": [profile_file],
            "output": "smaller",
        }
    ).model_dump(mode="json", by_alias=True, exclude_none=True, exclude_unset=True)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/compressed-pdf":
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
            assert request.url.params["format"] == "info"
            return httpx.Response(
                200,
                json=build_file_info_payload(
                    output_id,
                    "smaller.pdf",
                    "application/pdf",
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.compress_pdf(
            input_file,
            compression_level="custom",
            profile=profile_file,
            output="smaller",
        )

    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.output_file.name == "smaller.pdf"


def test_compress_pdf_request_customization(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(1))
    profile_file = make_profile_file(str(PdfRestFileID.generate()))
    output_id = str(PdfRestFileID.generate())
    captured_timeout: dict[str, float | dict[str, float] | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/compressed-pdf":
            assert request.url.params["trace"] == "sync"
            assert request.headers["X-Debug"] == "sync"
            captured_timeout["value"] = request.extensions.get("timeout")
            payload = json.loads(request.content.decode("utf-8"))
            assert payload["compression_level"] == "custom"
            assert payload["profile_id"] == str(profile_file.id)
            assert payload["output"] == "custom-name"
            assert payload["diagnostics"] == "on"
            return httpx.Response(
                200,
                json={
                    "inputId": [input_file.id],
                    "outputId": [output_id],
                },
            )
        if request.method == "GET" and request.url.path == f"/resource/{output_id}":
            assert request.url.params["format"] == "info"
            assert request.url.params["trace"] == "sync"
            assert request.headers["X-Debug"] == "sync"
            return httpx.Response(
                200,
                json=build_file_info_payload(
                    output_id,
                    "custom-name.pdf",
                    "application/pdf",
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.compress_pdf(
            input_file,
            compression_level="custom",
            profile=[profile_file],
            output="custom-name",
            extra_query={"trace": "sync"},
            extra_headers={"X-Debug": "sync"},
            extra_body={"diagnostics": "on"},
            timeout=0.42,
        )

    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.output_file.name == "custom-name.pdf"
    timeout_value = captured_timeout["value"]
    assert timeout_value is not None
    if isinstance(timeout_value, dict):
        assert all(pytest.approx(0.42) == value for value in timeout_value.values())
    else:
        assert timeout_value == pytest.approx(0.42)


@pytest.mark.asyncio
async def test_async_compress_pdf_request_customization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(2))
    profile_file = make_profile_file(str(PdfRestFileID.generate()))
    output_id = str(PdfRestFileID.generate())
    captured_timeout: dict[str, float | dict[str, float] | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/compressed-pdf":
            assert request.url.params["trace"] == "async"
            assert request.headers["X-Debug"] == "async"
            captured_timeout["value"] = request.extensions.get("timeout")
            payload = json.loads(request.content.decode("utf-8"))
            assert payload["compression_level"] == "custom"
            assert payload["profile_id"] == str(profile_file.id)
            assert payload["output"] == "async-custom-name"
            assert payload["diagnostics"] == "on"
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
                    "async-custom-name.pdf",
                    "application/pdf",
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        response = await client.compress_pdf(
            input_file,
            compression_level="custom",
            profile=[profile_file],
            output="async-custom-name",
            extra_query={"trace": "async"},
            extra_headers={"X-Debug": "async"},
            extra_body={"diagnostics": "on"},
            timeout=0.88,
        )

    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.output_file.name == "async-custom-name.pdf"
    timeout_value = captured_timeout["value"]
    assert timeout_value is not None
    if isinstance(timeout_value, dict):
        assert all(pytest.approx(0.88) == value for value in timeout_value.values())
    else:
        assert timeout_value == pytest.approx(0.88)


@pytest.mark.asyncio
async def test_async_compress_pdf_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(2))
    output_id = str(PdfRestFileID.generate())

    payload_dump = PdfCompressPayload.model_validate(
        {"files": [input_file], "compression_level": "medium"}
    ).model_dump(mode="json", by_alias=True, exclude_none=True, exclude_unset=True)

    seen: dict[str, int] = {"post": 0, "get": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/compressed-pdf":
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
                    "async.pdf",
                    "application/pdf",
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        response = await client.compress_pdf(
            input_file,
            compression_level="medium",
        )

    assert seen == {"post": 1, "get": 1}
    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.output_file.name == "async.pdf"


@pytest.mark.asyncio
async def test_async_compress_pdf_custom_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(2))
    profile_file = make_profile_file(str(PdfRestFileID.generate()))
    output_id = str(PdfRestFileID.generate())
    captured_timeout: dict[str, float | dict[str, float] | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/compressed-pdf":
            assert request.url.params["trace"] == "async"
            assert request.headers["X-Debug"] == "async"
            captured_timeout["value"] = request.extensions.get("timeout")
            payload = json.loads(request.content.decode("utf-8"))
            assert payload["profile_id"] == str(profile_file.id)
            assert payload["compression_level"] == "custom"
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
        response = await client.compress_pdf(
            input_file,
            compression_level="custom",
            profile=profile_file,
            extra_query={"trace": "async"},
            extra_headers={"X-Debug": "async"},
            timeout=0.77,
        )

    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.output_file.name == "async-custom.pdf"
    timeout_value = captured_timeout["value"]
    assert timeout_value is not None
    if isinstance(timeout_value, dict):
        assert all(pytest.approx(0.77) == value for value in timeout_value.values())
    else:
        assert timeout_value == pytest.approx(0.77)


def test_compress_pdf_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    pdf_file = make_pdf_file(PdfRestFileID.generate(1))
    non_pdf_file = PdfRestFile.model_validate(
        build_file_info_payload(
            PdfRestFileID.generate(),
            "example.png",
            "image/png",
        )
    )
    profile_file = make_profile_file(str(PdfRestFileID.generate()))
    bad_profile_file = make_pdf_file(PdfRestFileID.generate(1), name="example.pdf")
    transport = httpx.MockTransport(lambda request: (_ for _ in ()).throw(RuntimeError))

    with (
        PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client,
        pytest.raises(ValidationError, match="Must be a PDF file"),
    ):
        client.compress_pdf(non_pdf_file, compression_level="low")

    with (
        PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client,
        pytest.raises(
            ValidationError,
            match="compression_level 'custom' requires a profile",
        ),
    ):
        client.compress_pdf(pdf_file, compression_level="custom")

    with (
        PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client,
        pytest.raises(
            ValidationError,
            match="Profile must be a JSON file",
        ),
    ):
        client.compress_pdf(
            pdf_file,
            compression_level="custom",
            profile=bad_profile_file,
        )

    with (
        PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client,
        pytest.raises(
            ValidationError,
            match="A profile can only be provided when compression_level is 'custom'",
        ),
    ):
        client.compress_pdf(
            pdf_file,
            compression_level="low",
            profile=profile_file,
        )


def test_compress_pdf_requires_profile_for_custom_sync(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    pdf_file = make_pdf_file(PdfRestFileID.generate(1))
    transport = httpx.MockTransport(lambda request: (_ for _ in ()).throw(RuntimeError))

    with (
        PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client,
        pytest.raises(
            ValidationError,
            match="compression_level 'custom' requires a profile",
        ),
    ):
        client.compress_pdf(pdf_file, compression_level="custom")


@pytest.mark.asyncio
async def test_async_compress_pdf_requires_profile_for_custom(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    pdf_file = make_pdf_file(PdfRestFileID.generate(1))
    transport = httpx.MockTransport(lambda request: (_ for _ in ()).throw(RuntimeError))

    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        with pytest.raises(
            ValidationError,
            match="compression_level 'custom' requires a profile",
        ):
            await client.compress_pdf(pdf_file, compression_level="custom")


def test_compress_pdf_rejects_profile_for_presets_sync(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    pdf_file = make_pdf_file(PdfRestFileID.generate(1))
    profile_file = make_profile_file(str(PdfRestFileID.generate()))
    transport = httpx.MockTransport(lambda request: (_ for _ in ()).throw(RuntimeError))

    with (
        PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client,
        pytest.raises(
            ValidationError,
            match="A profile can only be provided when compression_level is 'custom'",
        ),
    ):
        client.compress_pdf(
            pdf_file,
            compression_level="low",
            profile=profile_file,
        )


@pytest.mark.asyncio
async def test_async_compress_pdf_rejects_profile_for_presets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    pdf_file = make_pdf_file(PdfRestFileID.generate(1))
    profile_file = make_profile_file(str(PdfRestFileID.generate()))
    transport = httpx.MockTransport(lambda request: (_ for _ in ()).throw(RuntimeError))

    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        with pytest.raises(
            ValidationError,
            match="A profile can only be provided when compression_level is 'custom'",
        ):
            await client.compress_pdf(
                pdf_file,
                compression_level="low",
                profile=profile_file,
            )


@pytest.mark.asyncio
async def test_async_compress_pdf_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    pdf_file = make_pdf_file(PdfRestFileID.generate(1))
    non_pdf_file = PdfRestFile.model_validate(
        build_file_info_payload(
            PdfRestFileID.generate(),
            "example.png",
            "image/png",
        )
    )
    profile_file = make_profile_file(str(PdfRestFileID.generate()))
    bad_profile_file = make_pdf_file(PdfRestFileID.generate(1), name="example.pdf")
    transport = httpx.MockTransport(lambda request: (_ for _ in ()).throw(RuntimeError))

    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        with pytest.raises(ValidationError, match="Must be a PDF file"):
            await client.compress_pdf(non_pdf_file, compression_level="low")

        with pytest.raises(
            ValidationError,
            match="compression_level 'custom' requires a profile",
        ):
            await client.compress_pdf(pdf_file, compression_level="custom")

        with pytest.raises(ValidationError, match="Profile must be a JSON file"):
            await client.compress_pdf(
                pdf_file,
                compression_level="custom",
                profile=bad_profile_file,
            )

        with pytest.raises(
            ValidationError,
            match="A profile can only be provided when compression_level is 'custom'",
        ):
            await client.compress_pdf(
                pdf_file,
                compression_level="low",
                profile=profile_file,
            )
