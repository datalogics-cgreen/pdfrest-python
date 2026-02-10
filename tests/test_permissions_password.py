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
from pdfrest.models._internal import PdfRestrictPayload, PdfUnrestrictPayload
from pdfrest.types import PdfRestriction

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


def build_restrict_payload(
    input_file: PdfRestFile,
    *,
    new_permissions_password: str,
    current_permissions_password: str | None = None,
    current_open_password: str | None = None,
    restrictions: list[PdfRestriction] | None = None,
    output: str | None = None,
) -> dict[str, object]:
    return PdfRestrictPayload.model_validate(
        {
            "files": [input_file],
            "new_permissions_password": new_permissions_password,
            "current_permissions_password": current_permissions_password,
            "current_open_password": current_open_password,
            "restrictions": restrictions,
            "output": output,
        }
    ).model_dump(mode="json", by_alias=True, exclude_none=True, exclude_unset=True)


def build_unrestrict_payload(
    input_file: PdfRestFile,
    *,
    current_permissions_password: str,
    current_open_password: str | None = None,
    output: str | None = None,
) -> dict[str, object]:
    return PdfUnrestrictPayload.model_validate(
        {
            "files": [input_file],
            "current_permissions_password": current_permissions_password,
            "current_open_password": current_open_password,
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
    "restrictions",
    [
        pytest.param(None, id="none"),
        pytest.param(["print_low"], id="single"),
        pytest.param(["print_low", "copy_content"], id="multiple"),
    ],
)
def test_add_permissions_password_success(
    monkeypatch: pytest.MonkeyPatch, restrictions: list[PdfRestriction] | None
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(1))
    output_id = str(PdfRestFileID.generate())
    new_password = make_password("secure")
    open_password = make_password("open")
    payload_dump = build_restrict_payload(
        input_file,
        new_permissions_password=new_password,
        current_open_password=open_password,
        restrictions=restrictions,
        output="restricted",
    )

    seen: dict[str, int] = {"post": 0, "get": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/restricted-pdf":
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
                    "restricted.pdf",
                    "application/pdf",
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.add_permissions_password(
            input_file,
            new_permissions_password=new_password,
            restrictions=restrictions,
            current_open_password=open_password,
            output="restricted",
        )

    assert seen == {"post": 1, "get": 1}
    assert_pdf_file_response(
        response,
        expected_name="restricted.pdf",
        input_file=input_file,
    )


def test_add_permissions_password_request_customization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(1))
    output_id = str(PdfRestFileID.generate())
    captured_timeout: dict[str, float | dict[str, float] | None] = {}
    new_password = make_password("custom")
    payload_dump = build_restrict_payload(
        input_file,
        new_permissions_password=new_password,
        restrictions=["print_high"],
        output="custom-restricted",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/restricted-pdf":
            assert request.url.params["trace"] == "sync"
            assert request.headers["X-Debug"] == "sync"
            captured_timeout["value"] = request.extensions.get("timeout")
            payload = json.loads(request.content.decode("utf-8"))
            assert payload == {**payload_dump, "keep_open": "yes"}
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
                    "custom-restricted.pdf",
                    "application/pdf",
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.add_permissions_password(
            input_file,
            new_permissions_password=new_password,
            restrictions=["print_high"],
            output="custom-restricted",
            extra_query={"trace": "sync"},
            extra_headers={"X-Debug": "sync"},
            extra_body={"keep_open": "yes"},
            timeout=0.55,
        )

    assert_pdf_file_response(
        response,
        expected_name="custom-restricted.pdf",
        input_file=input_file,
    )
    timeout_value = captured_timeout["value"]
    assert timeout_value is not None
    if isinstance(timeout_value, dict):
        assert all(pytest.approx(0.55) == value for value in timeout_value.values())
    else:
        assert timeout_value == pytest.approx(0.55)


def test_change_permissions_password_request_customization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(1))
    output_id = str(PdfRestFileID.generate())
    captured_timeout: dict[str, float | dict[str, float] | None] = {}
    current_password = make_password("old")
    new_password = make_password("new")
    current_open_password = make_password("open")
    payload_dump = build_restrict_payload(
        input_file,
        current_permissions_password=current_password,
        new_permissions_password=new_password,
        current_open_password=current_open_password,
        restrictions=["edit_content"],
        output="rotated",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/restricted-pdf":
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
                    "rotated.pdf",
                    "application/pdf",
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.change_permissions_password(
            input_file,
            current_permissions_password=current_password,
            new_permissions_password=new_password,
            current_open_password=current_open_password,
            restrictions=["edit_content"],
            output="rotated",
            extra_query={"trace": "sync"},
            extra_headers={"X-Debug": "sync"},
            extra_body={"diagnostics": "on"},
            timeout=0.77,
        )

    assert_pdf_file_response(
        response,
        expected_name="rotated.pdf",
        input_file=input_file,
    )
    timeout_value = captured_timeout["value"]
    assert timeout_value is not None
    if isinstance(timeout_value, dict):
        assert all(pytest.approx(0.77) == value for value in timeout_value.values())
    else:
        assert timeout_value == pytest.approx(0.77)


def test_remove_permissions_password_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(1))
    output_id = str(PdfRestFileID.generate())
    current_password = make_password("old")
    payload_dump = build_unrestrict_payload(
        input_file,
        current_permissions_password=current_password,
        output="clean",
    )

    seen: dict[str, int] = {"post": 0, "get": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/unrestricted-pdf":
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
                    "clean.pdf",
                    "application/pdf",
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.remove_permissions_password(
            input_file,
            current_permissions_password=current_password,
            output="clean",
        )

    assert seen == {"post": 1, "get": 1}
    assert_pdf_file_response(
        response,
        expected_name="clean.pdf",
        input_file=input_file,
    )


def test_remove_permissions_password_request_customization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(1))
    output_id = str(PdfRestFileID.generate())
    captured_timeout: dict[str, float | dict[str, float] | None] = {}
    current_password = make_password("remove-custom")
    open_password = make_password("open-custom")
    payload_dump = build_unrestrict_payload(
        input_file,
        current_permissions_password=current_password,
        current_open_password=open_password,
        output="clean-custom",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/unrestricted-pdf":
            assert request.url.params["trace"] == "sync"
            assert request.headers["X-Debug"] == "sync"
            captured_timeout["value"] = request.extensions.get("timeout")
            payload = json.loads(request.content.decode("utf-8"))
            assert payload == {**payload_dump, "audit": "enabled"}
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
                    "clean-custom.pdf",
                    "application/pdf",
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.remove_permissions_password(
            input_file,
            current_permissions_password=current_password,
            current_open_password=open_password,
            output="clean-custom",
            extra_query={"trace": "sync"},
            extra_headers={"X-Debug": "sync"},
            extra_body={"audit": "enabled"},
            timeout=0.69,
        )

    assert_pdf_file_response(
        response,
        expected_name="clean-custom.pdf",
        input_file=input_file,
    )
    timeout_value = captured_timeout["value"]
    assert timeout_value is not None
    if isinstance(timeout_value, dict):
        assert all(pytest.approx(0.69) == value for value in timeout_value.values())
    else:
        assert timeout_value == pytest.approx(0.69)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "restrictions",
    [
        pytest.param(None, id="none"),
        pytest.param(["print_low"], id="single"),
        pytest.param(["print_low", "copy_content"], id="multiple"),
    ],
)
async def test_async_add_permissions_password_success(
    monkeypatch: pytest.MonkeyPatch, restrictions: list[PdfRestriction] | None
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(1))
    output_id = str(PdfRestFileID.generate())
    new_password = make_password("secure")
    payload_dump = build_restrict_payload(
        input_file,
        new_permissions_password=new_password,
        restrictions=restrictions,
        output="restricted",
    )

    seen: dict[str, int] = {"post": 0, "get": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/restricted-pdf":
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
                    "restricted.pdf",
                    "application/pdf",
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        response = await client.add_permissions_password(
            input_file,
            new_permissions_password=new_password,
            restrictions=restrictions,
            output="restricted",
        )

    assert seen == {"post": 1, "get": 1}
    assert_pdf_file_response(
        response,
        expected_name="restricted.pdf",
        input_file=input_file,
    )


@pytest.mark.asyncio
async def test_async_add_permissions_password_request_customization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(2))
    output_id = str(PdfRestFileID.generate())
    captured_timeout: dict[str, float | dict[str, float] | None] = {}
    new_password = make_password("async")
    current_open_password = make_password("async-open")
    payload_dump = build_restrict_payload(
        input_file,
        new_permissions_password=new_password,
        current_open_password=current_open_password,
        restrictions=["print_high"],
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/restricted-pdf":
            assert request.url.params["trace"] == "async"
            assert request.headers["X-Debug"] == "async"
            captured_timeout["value"] = request.extensions.get("timeout")
            payload = json.loads(request.content.decode("utf-8"))
            assert payload == {**payload_dump, "keep_open": "yes"}
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
                    "async-restricted.pdf",
                    "application/pdf",
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        response = await client.add_permissions_password(
            input_file,
            new_permissions_password=new_password,
            current_open_password=current_open_password,
            restrictions=["print_high"],
            extra_query={"trace": "async"},
            extra_headers={"X-Debug": "async"},
            extra_body={"keep_open": "yes"},
            timeout=0.66,
        )

    assert_pdf_file_response(
        response,
        expected_name="async-restricted.pdf",
        input_file=input_file,
    )
    timeout_value = captured_timeout["value"]
    assert timeout_value is not None
    if isinstance(timeout_value, dict):
        assert all(pytest.approx(0.66) == value for value in timeout_value.values())
    else:
        assert timeout_value == pytest.approx(0.66)


@pytest.mark.asyncio
async def test_async_change_permissions_password_request_customization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(2))
    output_id = str(PdfRestFileID.generate())
    captured_timeout: dict[str, float | dict[str, float] | None] = {}
    current_password = make_password("old-async")
    new_password = make_password("new-async")
    current_open_password = make_password("open-async")
    payload_dump = build_restrict_payload(
        input_file,
        current_permissions_password=current_password,
        new_permissions_password=new_password,
        current_open_password=current_open_password,
        restrictions=["edit_content"],
        output="async-rotated",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/restricted-pdf":
            assert request.url.params["trace"] == "async"
            assert request.headers["X-Debug"] == "async"
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
            assert request.url.params["trace"] == "async"
            assert request.headers["X-Debug"] == "async"
            return httpx.Response(
                200,
                json=build_file_info_payload(
                    output_id,
                    "async-rotated.pdf",
                    "application/pdf",
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        response = await client.change_permissions_password(
            input_file,
            current_permissions_password=current_password,
            new_permissions_password=new_password,
            current_open_password=current_open_password,
            restrictions=["edit_content"],
            output="async-rotated",
            extra_query={"trace": "async"},
            extra_headers={"X-Debug": "async"},
            extra_body={"diagnostics": "on"},
            timeout=0.88,
        )

    assert_pdf_file_response(
        response,
        expected_name="async-rotated.pdf",
        input_file=input_file,
    )
    timeout_value = captured_timeout["value"]
    assert timeout_value is not None
    if isinstance(timeout_value, dict):
        assert all(pytest.approx(0.88) == value for value in timeout_value.values())
    else:
        assert timeout_value == pytest.approx(0.88)


@pytest.mark.asyncio
async def test_async_remove_permissions_password_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(2))
    output_id = str(PdfRestFileID.generate())
    current_password = make_password("secret")
    payload_dump = build_unrestrict_payload(
        input_file,
        current_permissions_password=current_password,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/unrestricted-pdf":
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
                    "async-clean.pdf",
                    "application/pdf",
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        response = await client.remove_permissions_password(
            input_file,
            current_permissions_password=current_password,
        )

    assert_pdf_file_response(
        response,
        expected_name="async-clean.pdf",
        input_file=input_file,
    )


@pytest.mark.asyncio
async def test_async_remove_permissions_password_request_customization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(2))
    output_id = str(PdfRestFileID.generate())
    captured_timeout: dict[str, float | dict[str, float] | None] = {}
    current_password = make_password("async-remove-custom")
    open_password = make_password("async-open-custom")
    payload_dump = build_unrestrict_payload(
        input_file,
        current_permissions_password=current_password,
        current_open_password=open_password,
        output="async-clean-custom",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/unrestricted-pdf":
            assert request.url.params["trace"] == "async"
            assert request.headers["X-Debug"] == "async"
            captured_timeout["value"] = request.extensions.get("timeout")
            payload = json.loads(request.content.decode("utf-8"))
            assert payload == {**payload_dump, "audit": "enabled"}
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
                    "async-clean-custom.pdf",
                    "application/pdf",
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        response = await client.remove_permissions_password(
            input_file,
            current_permissions_password=current_password,
            current_open_password=open_password,
            output="async-clean-custom",
            extra_query={"trace": "async"},
            extra_headers={"X-Debug": "async"},
            extra_body={"audit": "enabled"},
            timeout=0.73,
        )

    assert_pdf_file_response(
        response,
        expected_name="async-clean-custom.pdf",
        input_file=input_file,
    )
    timeout_value = captured_timeout["value"]
    assert timeout_value is not None
    if isinstance(timeout_value, dict):
        assert all(pytest.approx(0.73) == value for value in timeout_value.values())
    else:
        assert timeout_value == pytest.approx(0.73)


@pytest.mark.asyncio
async def test_async_permissions_password_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    pdf_file = make_pdf_file(PdfRestFileID.generate(1))
    non_pdf_file = make_non_pdf_file(str(PdfRestFileID.generate()))
    other_pdf = make_pdf_file(PdfRestFileID.generate(2))
    secure_password = make_password("secure")
    another_password = make_password("another")
    empty_password = "".join([])
    transport = httpx.MockTransport(lambda request: (_ for _ in ()).throw(RuntimeError))

    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        with pytest.raises(ValidationError, match="Must be a PDF file"):
            await client.add_permissions_password(
                non_pdf_file,
                new_permissions_password=secure_password,
            )

        with pytest.raises(ValidationError, match="at most 1"):
            await client.add_permissions_password(
                [pdf_file, other_pdf],
                new_permissions_password=secure_password,
            )

        with pytest.raises(
            ValidationError, match="String should have at least 6 characters"
        ):
            await client.add_permissions_password(
                pdf_file,
                new_permissions_password="a" * 5,
            )

        with pytest.raises(
            ValidationError, match="List should have at least 1 item after validation"
        ):
            await client.add_permissions_password(
                pdf_file,
                new_permissions_password=secure_password,
                restrictions=[],
            )

        with pytest.raises(
            ValidationError, match="String should have at least 1 character"
        ):
            await client.remove_permissions_password(
                pdf_file,
                current_permissions_password=empty_password,
            )

        with pytest.raises(ValidationError, match="at most 1"):
            await client.remove_permissions_password(
                [pdf_file, other_pdf],
                current_permissions_password=another_password,
            )


def test_permissions_password_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    pdf_file = make_pdf_file(PdfRestFileID.generate(1))
    non_pdf_file = make_non_pdf_file(str(PdfRestFileID.generate()))
    other_pdf = make_pdf_file(PdfRestFileID.generate(2))
    secure_password = make_password("secure")
    another_password = make_password("another")
    empty_password = "".join([])
    transport = httpx.MockTransport(lambda request: (_ for _ in ()).throw(RuntimeError))

    with (
        PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client,
        pytest.raises(ValidationError, match="Must be a PDF file"),
    ):
        client.add_permissions_password(
            non_pdf_file,
            new_permissions_password=secure_password,
        )

    with (
        PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client,
        pytest.raises(ValidationError, match="at most 1"),
    ):
        client.add_permissions_password(
            [pdf_file, other_pdf],
            new_permissions_password=secure_password,
        )

    with (
        PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client,
        pytest.raises(
            ValidationError, match="String should have at least 6 characters"
        ),
    ):
        client.add_permissions_password(
            pdf_file,
            new_permissions_password="a" * 5,
        )

    with (
        PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client,
        pytest.raises(
            ValidationError, match="List should have at least 1 item after validation"
        ),
    ):
        client.add_permissions_password(
            pdf_file,
            new_permissions_password=secure_password,
            restrictions=[],
        )

    with (
        PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client,
        pytest.raises(ValidationError, match="String should have at least 1 character"),
    ):
        client.remove_permissions_password(
            pdf_file,
            current_permissions_password=empty_password,
        )

    with (
        PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client,
        pytest.raises(ValidationError, match="at most 1"),
    ):
        client.remove_permissions_password(
            [pdf_file, other_pdf],
            current_permissions_password=another_password,
        )
