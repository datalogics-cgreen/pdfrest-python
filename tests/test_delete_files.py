from __future__ import annotations

import json

import httpx
import pytest
from pydantic import ValidationError

from pdfrest import AsyncPdfRestClient, PdfRestClient
from pdfrest.models import PdfRestDeletionResponse, PdfRestFileID
from pdfrest.models._internal import DeletePayload

from .graphics_test_helpers import ASYNC_API_KEY, VALID_API_KEY, make_pdf_file


def test_delete_payload_serialization() -> None:
    first = make_pdf_file(PdfRestFileID.generate(1))
    second = make_pdf_file(PdfRestFileID.generate(2))

    payload = DeletePayload.model_validate({"files": [first, second]})
    payload_dump = payload.model_dump(
        mode="json", by_alias=True, exclude_none=True, exclude_unset=True
    )

    assert payload_dump == {"ids": f"{first.id},{second.id}"}


def test_delete_payload_rejects_empty() -> None:
    with pytest.raises(ValidationError):
        DeletePayload.model_validate({"files": []})


def test_delete_files_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    file_repr = make_pdf_file(PdfRestFileID.generate(1))
    payload_dump = DeletePayload.model_validate({"files": [file_repr]}).model_dump(
        mode="json", by_alias=True, exclude_none=True, exclude_unset=True
    )

    seen: dict[str, int] = {"post": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/delete":
            seen["post"] += 1
            payload = json.loads(request.content.decode("utf-8"))
            assert payload == payload_dump
            return httpx.Response(
                200,
                json={
                    "deletionResponses": {
                        str(file_repr.id): "Successfully Deleted",
                    }
                },
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.files.delete(file_repr)

    assert seen == {"post": 1}
    assert isinstance(response, PdfRestDeletionResponse)
    assert response.deletion_responses[str(file_repr.id)] == "Successfully Deleted"


def test_delete_files_request_customization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    file_repr = make_pdf_file(PdfRestFileID.generate(1))
    captured_timeout: dict[str, float | dict[str, float] | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/delete":
            assert request.url.params["trace"] == "true"
            assert request.headers["X-Debug"] == "sync"
            captured_timeout["value"] = request.extensions.get("timeout")
            payload = json.loads(request.content.decode("utf-8"))
            assert payload["ids"] == str(file_repr.id)
            assert payload["debug"] is True
            return httpx.Response(
                200,
                json={
                    "deletionResponses": {
                        str(file_repr.id): "Successfully Deleted",
                    }
                },
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.files.delete(
            file_repr,
            extra_query={"trace": "true"},
            extra_headers={"X-Debug": "sync"},
            extra_body={"debug": True},
            timeout=0.3,
        )

    assert isinstance(response, PdfRestDeletionResponse)
    timeout_value = captured_timeout["value"]
    assert timeout_value is not None
    if isinstance(timeout_value, dict):
        assert all(
            component == pytest.approx(0.3) for component in timeout_value.values()
        )
    else:
        assert timeout_value == pytest.approx(0.3)


@pytest.mark.asyncio
async def test_async_delete_files_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    file_repr = make_pdf_file(PdfRestFileID.generate(2))
    payload_dump = DeletePayload.model_validate({"files": [file_repr]}).model_dump(
        mode="json", by_alias=True, exclude_none=True, exclude_unset=True
    )

    seen: dict[str, int] = {"post": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/delete":
            seen["post"] += 1
            payload = json.loads(request.content.decode("utf-8"))
            assert payload == payload_dump
            return httpx.Response(
                200,
                json={
                    "deletionResponses": {
                        str(file_repr.id): "Successfully Deleted",
                    }
                },
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    async with AsyncPdfRestClient(
        api_key=ASYNC_API_KEY,
        transport=transport,
    ) as client:
        response = await client.files.delete(file_repr)

    assert seen == {"post": 1}
    assert isinstance(response, PdfRestDeletionResponse)
    assert response.deletion_responses[str(file_repr.id)] == "Successfully Deleted"
