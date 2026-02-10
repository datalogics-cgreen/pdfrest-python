from __future__ import annotations

import json
from uuid import uuid4

import httpx
import pytest
from pydantic import ValidationError

from pdfrest import AsyncPdfRestClient, PdfRestClient
from pdfrest.models import (
    PdfRestFile,
    PdfRestFileBasedResponse,
    PdfRestFileID,
)
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


def build_encrypt_payload(
    input_file: PdfRestFile,
    *,
    new_open_password: str,
    current_open_password: str | None = None,
    current_permissions_password: str | None = None,
    output: str | None = None,
) -> dict[str, object]:
    return PdfEncryptPayload.model_validate(
        {
            "files": [input_file],
            "new_open_password": new_open_password,
            "current_open_password": current_open_password,
            "current_permissions_password": current_permissions_password,
            "output": output,
        }
    ).model_dump(mode="json", by_alias=True, exclude_none=True, exclude_unset=True)


def build_decrypt_payload(
    input_file: PdfRestFile,
    *,
    current_open_password: str,
    current_permissions_password: str | None = None,
    output: str | None = None,
) -> dict[str, object]:
    return PdfDecryptPayload.model_validate(
        {
            "files": [input_file],
            "current_open_password": current_open_password,
            "current_permissions_password": current_permissions_password,
            "output": output,
        }
    ).model_dump(mode="json", by_alias=True, exclude_none=True, exclude_unset=True)


def assert_pdf_file_response(
    response: PdfRestFileBasedResponse, *, expected_name: str, input_file: PdfRestFile
) -> None:
    assert isinstance(response, PdfRestFileBasedResponse)
    output_file = response.output_file
    assert output_file.name == expected_name
    assert output_file.type == "application/pdf"
    assert output_file.size > 0
    output_url = str(output_file.url)
    assert f"/resource/{output_file.id}" in output_url
    assert response.warning is None
    assert str(response.input_id) == str(input_file.id)


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
    payload_dump = build_encrypt_payload(
        input_file,
        new_open_password=new_password,
        current_permissions_password=permissions_password,
        output="encrypted",
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
    assert_pdf_file_response(
        response,
        expected_name="encrypted.pdf",
        input_file=input_file,
    )


def test_add_open_password_request_customization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(1))
    output_id = str(PdfRestFileID.generate())
    captured_timeout: dict[str, float | dict[str, float] | None] = {}
    new_password = make_password("open-custom")
    permissions_password = make_password("perm-custom")
    payload_dump = build_encrypt_payload(
        input_file,
        new_open_password=new_password,
        current_permissions_password=permissions_password,
        output="encrypted-custom",
    )

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
                    "encrypted-custom.pdf",
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
            output="encrypted-custom",
            extra_query={"trace": "sync"},
            extra_headers={"X-Debug": "sync"},
            extra_body={"diagnostics": "on"},
            timeout=0.71,
        )

    assert_pdf_file_response(
        response,
        expected_name="encrypted-custom.pdf",
        input_file=input_file,
    )
    timeout_value = captured_timeout["value"]
    assert timeout_value is not None
    if isinstance(timeout_value, dict):
        assert all(pytest.approx(0.71) == value for value in timeout_value.values())
    else:
        assert timeout_value == pytest.approx(0.71)


def test_change_open_password_request_customization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(1))
    output_id = str(PdfRestFileID.generate())
    captured_timeout: dict[str, float | dict[str, float] | None] = {}
    current_password = make_password("old-open")
    new_password = make_password("new-open")
    permissions_password = make_password("perm")
    payload_dump = build_encrypt_payload(
        input_file,
        current_open_password=current_password,
        new_open_password=new_password,
        current_permissions_password=permissions_password,
        output="rotated-open",
    )

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
            current_permissions_password=permissions_password,
            output="rotated-open",
            extra_query={"trace": "sync"},
            extra_headers={"X-Debug": "sync"},
            extra_body={"diagnostics": "on"},
            timeout=0.77,
        )

    assert_pdf_file_response(
        response,
        expected_name="rotated-open.pdf",
        input_file=input_file,
    )
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
    payload_dump = build_decrypt_payload(
        input_file,
        current_open_password=current_password,
        output="decrypted",
    )

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
    assert_pdf_file_response(
        response,
        expected_name="decrypted.pdf",
        input_file=input_file,
    )


def test_remove_open_password_request_customization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(1))
    output_id = str(PdfRestFileID.generate())
    captured_timeout: dict[str, float | dict[str, float] | None] = {}
    current_password = make_password("open-custom")
    permissions_password = make_password("perm-custom")
    payload_dump = build_decrypt_payload(
        input_file,
        current_open_password=current_password,
        current_permissions_password=permissions_password,
        output="decrypted-custom",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/decrypted-pdf":
            assert request.url.params["trace"] == "sync"
            assert request.headers["X-Debug"] == "sync"
            captured_timeout["value"] = request.extensions.get("timeout")
            payload = json.loads(request.content.decode("utf-8"))
            assert payload == {**payload_dump, "audit": "yes"}
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
                    "decrypted-custom.pdf",
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
            current_permissions_password=permissions_password,
            output="decrypted-custom",
            extra_query={"trace": "sync"},
            extra_headers={"X-Debug": "sync"},
            extra_body={"audit": "yes"},
            timeout=0.59,
        )

    assert_pdf_file_response(
        response,
        expected_name="decrypted-custom.pdf",
        input_file=input_file,
    )
    timeout_value = captured_timeout["value"]
    assert timeout_value is not None
    if isinstance(timeout_value, dict):
        assert all(pytest.approx(0.59) == value for value in timeout_value.values())
    else:
        assert timeout_value == pytest.approx(0.59)


@pytest.mark.asyncio
async def test_async_add_open_password_request_customization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(2))
    output_id = str(PdfRestFileID.generate())
    captured_timeout: dict[str, float | dict[str, float] | None] = {}
    new_password = make_password("async-open")
    permissions_password = make_password("async-perm")
    payload_dump = build_encrypt_payload(
        input_file,
        new_open_password=new_password,
        current_permissions_password=permissions_password,
        output="async-encrypted",
    )

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
            current_permissions_password=permissions_password,
            output="async-encrypted",
            extra_query={"trace": "async"},
            extra_headers={"X-Debug": "async"},
            extra_body={"keep_permissions": "yes"},
            timeout=0.66,
        )

    assert_pdf_file_response(
        response,
        expected_name="async-encrypted.pdf",
        input_file=input_file,
    )
    timeout_value = captured_timeout["value"]
    assert timeout_value is not None
    if isinstance(timeout_value, dict):
        assert all(pytest.approx(0.66) == value for value in timeout_value.values())
    else:
        assert timeout_value == pytest.approx(0.66)


@pytest.mark.asyncio
async def test_async_change_open_password_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(2))
    output_id = str(PdfRestFileID.generate())
    current_password = make_password("async-open-current")
    new_password = make_password("async-open-next")
    permissions_password = make_password("async-open-perm")
    payload_dump = build_encrypt_payload(
        input_file,
        current_open_password=current_password,
        new_open_password=new_password,
        current_permissions_password=permissions_password,
        output="async-rotated-open",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/encrypted-pdf":
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
                    "async-rotated-open.pdf",
                    "application/pdf",
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        response = await client.change_open_password(
            input_file,
            current_open_password=current_password,
            new_open_password=new_password,
            current_permissions_password=permissions_password,
            output="async-rotated-open",
        )

    assert_pdf_file_response(
        response,
        expected_name="async-rotated-open.pdf",
        input_file=input_file,
    )


@pytest.mark.asyncio
async def test_async_change_open_password_request_customization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(2))
    output_id = str(PdfRestFileID.generate())
    captured_timeout: dict[str, float | dict[str, float] | None] = {}
    current_password = make_password("async-open-current-custom")
    new_password = make_password("async-open-next-custom")
    permissions_password = make_password("async-open-perm-custom")
    payload_dump = build_encrypt_payload(
        input_file,
        current_open_password=current_password,
        new_open_password=new_password,
        current_permissions_password=permissions_password,
        output="async-rotated-open-custom",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/encrypted-pdf":
            assert request.url.params["trace"] == "async"
            assert request.headers["X-Debug"] == "async"
            captured_timeout["value"] = request.extensions.get("timeout")
            payload = json.loads(request.content.decode("utf-8"))
            assert payload == {**payload_dump, "audit": "yes"}
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
                    "async-rotated-open-custom.pdf",
                    "application/pdf",
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        response = await client.change_open_password(
            input_file,
            current_open_password=current_password,
            new_open_password=new_password,
            current_permissions_password=permissions_password,
            output="async-rotated-open-custom",
            extra_query={"trace": "async"},
            extra_headers={"X-Debug": "async"},
            extra_body={"audit": "yes"},
            timeout=0.74,
        )

    assert_pdf_file_response(
        response,
        expected_name="async-rotated-open-custom.pdf",
        input_file=input_file,
    )
    timeout_value = captured_timeout["value"]
    assert timeout_value is not None
    if isinstance(timeout_value, dict):
        assert all(pytest.approx(0.74) == value for value in timeout_value.values())
    else:
        assert timeout_value == pytest.approx(0.74)


@pytest.mark.asyncio
async def test_async_remove_open_password_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(2))
    output_id = str(PdfRestFileID.generate())
    current_password = make_password("async-open-current")
    payload_dump = build_decrypt_payload(
        input_file,
        current_open_password=current_password,
    )

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

    assert_pdf_file_response(
        response,
        expected_name="async-decrypted.pdf",
        input_file=input_file,
    )


@pytest.mark.asyncio
async def test_async_remove_open_password_request_customization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(2))
    output_id = str(PdfRestFileID.generate())
    captured_timeout: dict[str, float | dict[str, float] | None] = {}
    current_password = make_password("async-open-custom")
    permissions_password = make_password("async-perm-custom")
    payload_dump = build_decrypt_payload(
        input_file,
        current_open_password=current_password,
        current_permissions_password=permissions_password,
        output="async-decrypted-custom",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/decrypted-pdf":
            assert request.url.params["trace"] == "async"
            assert request.headers["X-Debug"] == "async"
            captured_timeout["value"] = request.extensions.get("timeout")
            payload = json.loads(request.content.decode("utf-8"))
            assert payload == {**payload_dump, "audit": "yes"}
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
                    "async-decrypted-custom.pdf",
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
            current_permissions_password=permissions_password,
            output="async-decrypted-custom",
            extra_query={"trace": "async"},
            extra_headers={"X-Debug": "async"},
            extra_body={"audit": "yes"},
            timeout=0.63,
        )

    assert_pdf_file_response(
        response,
        expected_name="async-decrypted-custom.pdf",
        input_file=input_file,
    )
    timeout_value = captured_timeout["value"]
    assert timeout_value is not None
    if isinstance(timeout_value, dict):
        assert all(pytest.approx(0.63) == value for value in timeout_value.values())
    else:
        assert timeout_value == pytest.approx(0.63)


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


@pytest.mark.asyncio
async def test_async_encrypt_decrypt_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    pdf_file = make_pdf_file(PdfRestFileID.generate(1))
    non_pdf_file = make_non_pdf_file(str(PdfRestFileID.generate()))
    other_pdf = make_pdf_file(PdfRestFileID.generate(2))
    secure_password = make_password("secure-async")
    short_password = "a" * 3
    empty_password = "".join([])
    transport = httpx.MockTransport(lambda request: (_ for _ in ()).throw(RuntimeError))

    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        with pytest.raises(ValidationError, match="Must be a PDF file"):
            await client.add_open_password(
                non_pdf_file,
                new_open_password=secure_password,
            )

        with pytest.raises(ValidationError, match="at most 1"):
            await client.add_open_password(
                [pdf_file, other_pdf],
                new_open_password=secure_password,
            )

        with pytest.raises(
            ValidationError, match="String should have at least 6 characters"
        ):
            await client.add_open_password(
                pdf_file,
                new_open_password=short_password,
            )

        with pytest.raises(
            ValidationError, match="String should have at least 1 character"
        ):
            await client.change_open_password(
                pdf_file,
                current_open_password=empty_password,
                new_open_password=secure_password,
            )

        with pytest.raises(ValidationError, match="at most 1"):
            await client.remove_open_password(
                [pdf_file, other_pdf],
                current_open_password=secure_password,
            )
