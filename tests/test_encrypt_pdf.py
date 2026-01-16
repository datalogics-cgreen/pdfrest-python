from __future__ import annotations

import json
from uuid import uuid4

import httpx
import pytest
from pydantic import ValidationError

from pdfrest import AsyncPdfRestClient, PdfRestClient
from pdfrest.models import PdfRestFile, PdfRestFileBasedResponse, PdfRestFileID
from pdfrest.models._internal import PdfDecryptPayload, PdfEncryptPayload

from .graphics_test_helpers import (
    ASYNC_API_KEY,
    VALID_API_KEY,
    build_file_info_payload,
    make_pdf_file,
)


def make_password(label: str) -> str:
    return f"{label}-{uuid4().hex}"


def make_non_pdf_file(file_id: str) -> PdfRestFile:
    return PdfRestFile.model_validate(
        build_file_info_payload(
            file_id,
            "example.png",
            "image/png",
        )
    )


@pytest.mark.parametrize(
    "permissions_password",
    [
        pytest.param(None, id="no-permissions"),
        pytest.param(make_password("perm"), id="with-permissions"),
    ],
)
def test_add_open_password_success(
    monkeypatch: pytest.MonkeyPatch, permissions_password: str | None
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(1))
    output_id = str(PdfRestFileID.generate())
    new_password = make_password("open")
    payload_input: dict[str, object] = {
        "files": [input_file],
        "new_open_password": new_password,
        "output": "encrypted",
    }
    if permissions_password is not None:
        payload_input["current_permissions_password"] = permissions_password
    payload_dump = PdfEncryptPayload.model_validate(payload_input).model_dump(
        mode="json", by_alias=True, exclude_none=True, exclude_unset=True
    )

    seen: dict[str, int] = {"post": 0, "get": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/encrypted-pdf":
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
                    "encrypted.pdf",
                    "application/pdf",
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.add_open_password(
            input_file,
            new_open_password=new_password,
            current_permissions_password=permissions_password,
            output="encrypted",
        )

    assert seen == {"post": 1, "get": 1}
    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.output_file.name == "encrypted.pdf"
    assert response.output_file.type == "application/pdf"
    assert str(response.input_id) == str(input_file.id)


def test_change_open_password_request_customization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(1))
    output_id = str(PdfRestFileID.generate())
    captured_timeout: dict[str, float | dict[str, float] | None] = {}
    current_password = make_password("old-open")
    new_password = make_password("new-open")
    payload_dump = PdfEncryptPayload.model_validate(
        {
            "files": [input_file],
            "current_open_password": current_password,
            "new_open_password": new_password,
            "current_permissions_password": make_password("perm"),
            "output": "rotated-open",
        }
    ).model_dump(mode="json", by_alias=True, exclude_none=True, exclude_unset=True)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/encrypted-pdf":
            assert request.url.params["trace"] == "sync"
            assert request.headers["X-Debug"] == "sync"
            captured_timeout["value"] = request.extensions.get("timeout")
            payload = json.loads(request.content.decode("utf-8"))
            assert payload == {**payload_dump, "diagnostics": "on"}
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
                    "rotated-open.pdf",
                    "application/pdf",
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.change_open_password(
            input_file,
            current_open_password=current_password,
            new_open_password=new_password,
            current_permissions_password=payload_dump.get(
                "current_permissions_password"
            ),
            output="rotated-open",
            extra_query={"trace": "sync"},
            extra_headers={"X-Debug": "sync"},
            extra_body={"diagnostics": "on"},
            timeout=0.77,
        )

    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.output_file.name == "rotated-open.pdf"
    timeout_value = captured_timeout["value"]
    assert timeout_value is not None
    if isinstance(timeout_value, dict):
        assert all(pytest.approx(0.77) == value for value in timeout_value.values())
    else:
        assert timeout_value == pytest.approx(0.77)


def test_remove_open_password_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(1))
    output_id = str(PdfRestFileID.generate())
    current_password = make_password("open-current")
    payload_dump = PdfDecryptPayload.model_validate(
        {
            "files": [input_file],
            "current_open_password": current_password,
            "output": "decrypted",
        }
    ).model_dump(mode="json", by_alias=True, exclude_none=True, exclude_unset=True)

    seen: dict[str, int] = {"post": 0, "get": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/decrypted-pdf":
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
                    "decrypted.pdf",
                    "application/pdf",
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.remove_open_password(
            input_file,
            current_open_password=current_password,
            output="decrypted",
        )

    assert seen == {"post": 1, "get": 1}
    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.output_file.name == "decrypted.pdf"
    assert response.output_file.type == "application/pdf"


@pytest.mark.asyncio
async def test_async_add_open_password_request_customization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(2))
    output_id = str(PdfRestFileID.generate())
    captured_timeout: dict[str, float | dict[str, float] | None] = {}
    new_password = make_password("async-open")
    payload_dump = PdfEncryptPayload.model_validate(
        {
            "files": [input_file],
            "new_open_password": new_password,
        }
    ).model_dump(mode="json", by_alias=True, exclude_none=True, exclude_unset=True)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/encrypted-pdf":
            assert request.url.params["trace"] == "async"
            assert request.headers["X-Debug"] == "async"
            captured_timeout["value"] = request.extensions.get("timeout")
            payload = json.loads(request.content.decode("utf-8"))
            assert payload == {**payload_dump, "keep_permissions": "yes"}
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
                    "async-encrypted.pdf",
                    "application/pdf",
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        response = await client.add_open_password(
            input_file,
            new_open_password=new_password,
            extra_query={"trace": "async"},
            extra_headers={"X-Debug": "async"},
            extra_body={"keep_permissions": "yes"},
            timeout=0.66,
        )

    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.output_file.name == "async-encrypted.pdf"
    timeout_value = captured_timeout["value"]
    assert timeout_value is not None
    if isinstance(timeout_value, dict):
        assert all(pytest.approx(0.66) == value for value in timeout_value.values())
    else:
        assert timeout_value == pytest.approx(0.66)


@pytest.mark.asyncio
async def test_async_remove_open_password_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(2))
    output_id = str(PdfRestFileID.generate())
    current_password = make_password("async-open-current")
    payload_dump = PdfDecryptPayload.model_validate(
        {
            "files": [input_file],
            "current_open_password": current_password,
        }
    ).model_dump(mode="json", by_alias=True, exclude_none=True, exclude_unset=True)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/decrypted-pdf":
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
                    "async-decrypted.pdf",
                    "application/pdf",
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        response = await client.remove_open_password(
            input_file,
            current_open_password=current_password,
        )

    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.output_file.name == "async-decrypted.pdf"


def test_encrypt_decrypt_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    pdf_file = make_pdf_file(PdfRestFileID.generate(1))
    non_pdf_file = make_non_pdf_file(str(PdfRestFileID.generate()))
    other_pdf = make_pdf_file(PdfRestFileID.generate(2))
    secure_password = make_password("secure")
    short_password = "a" * 3
    empty_password = "".join([])
    transport = httpx.MockTransport(lambda request: (_ for _ in ()).throw(RuntimeError))

    with (
        PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client,
        pytest.raises(ValidationError, match="Must be a PDF file"),
    ):
        client.add_open_password(
            non_pdf_file,
            new_open_password=secure_password,
        )

    with (
        PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client,
        pytest.raises(ValidationError, match="at most 1"),
    ):
        client.add_open_password(
            [pdf_file, other_pdf],
            new_open_password=secure_password,
        )

    with (
        PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client,
        pytest.raises(
            ValidationError, match="String should have at least 6 characters"
        ),
    ):
        client.add_open_password(
            pdf_file,
            new_open_password=short_password,
        )

    with (
        PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client,
        pytest.raises(ValidationError, match="String should have at least 1 character"),
    ):
        client.change_open_password(
            pdf_file,
            current_open_password=empty_password,
            new_open_password=secure_password,
        )

    with (
        PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client,
        pytest.raises(ValidationError, match="at most 1"),
    ):
        client.remove_open_password(
            [pdf_file, other_pdf],
            current_open_password=secure_password,
        )
