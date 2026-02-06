from __future__ import annotations

import json
from collections.abc import Mapping
from itertools import product

import httpx
import pytest
from pydantic import ValidationError

from pdfrest import AsyncPdfRestClient, PdfRestApiError, PdfRestClient
from pdfrest.models import ExtractedTextDocument, PdfRestFileID
from pdfrest.models._internal import ExtractTextPayload

from .graphics_test_helpers import ASYNC_API_KEY, VALID_API_KEY, make_pdf_file


def _make_extracted_text_document_payload(input_id: str) -> dict[str, object]:
    return {
        "inputId": input_id,
        "words": [
            {
                "text": "Hello",
                "page": 1,
                "coordinates": {
                    "topLeft": {"x": 1, "y": 2},
                    "topRight": {"x": 3, "y": 4},
                    "bottomLeft": {"x": 5, "y": 6},
                    "bottomRight": {"x": 7, "y": 8},
                },
                "style": {
                    "color": {"space": "DeviceRGB", "values": [0, 0, 0]},
                    "font": {"name": "Calibri", "size": 12},
                },
            }
        ],
        "fullText": {
            "pages": [
                {"page": 1, "text": "Hello world"},
                {"page": 2, "text": "Bye"},
            ]
        },
    }


FULL_TEXT_OPTIONS = ("off", "by_page", "document")
BOOL_OPTION_SETS = list(product([False, True], repeat=3))

EXTRACT_TEXT_OPTION_SETS = [
    pytest.param(
        {
            "full_text": full_text,
            "preserve_line_breaks": preserve,
            "word_style": word_style,
            "word_coordinates": word_coordinates,
        },
        id=f"{full_text}-plb-{int(preserve)}-ws-{int(word_style)}-wc-{int(word_coordinates)}",
    )
    for full_text in FULL_TEXT_OPTIONS
    for preserve, word_style, word_coordinates in BOOL_OPTION_SETS
]

PAGES_OPTION_SETS = [
    pytest.param(None, id="without-pages"),
    pytest.param(["1-2"], id="with-pages"),
]


@pytest.mark.parametrize("options", EXTRACT_TEXT_OPTION_SETS)
def test_extract_pdf_text_success(
    options: Mapping[str, bool | str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(1))
    base_payload: dict[str, object] = {
        "files": [input_file],
        "pages": ["1-2"],
        "output_type": "json",
    }
    payload_input = base_payload | dict(options)
    payload_dump = ExtractTextPayload.model_validate(payload_input).model_dump(
        mode="json",
        by_alias=True,
        exclude_none=True,
        exclude_unset=True,
    )

    expected_response = _make_extracted_text_document_payload(str(input_file.id))
    seen: dict[str, int] = {"post": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/extracted-text":
            seen["post"] += 1
            payload = json.loads(request.content.decode("utf-8"))
            assert payload == payload_dump
            return httpx.Response(200, json=expected_response)
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.extract_pdf_text(
            input_file,
            pages=["1-2"],
            full_text=options["full_text"],
            preserve_line_breaks=options["preserve_line_breaks"],
            word_style=options["word_style"],
            word_coordinates=options["word_coordinates"],
        )

    assert seen == {"post": 1}
    assert isinstance(response, ExtractedTextDocument)
    assert response.input_id == input_file.id
    assert response.model_dump(by_alias=True, exclude_none=True) == expected_response


def test_extract_pdf_text_request_customization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(1))
    payload_dump = ExtractTextPayload.model_validate(
        {
            "files": [input_file],
            "full_text": "document",
            "preserve_line_breaks": False,
            "word_style": False,
            "word_coordinates": False,
            "output_type": "json",
        }
    ).model_dump(mode="json", by_alias=True, exclude_none=True, exclude_unset=True)
    expected_response = _make_extracted_text_document_payload(str(input_file.id))
    captured_timeout: dict[str, float | dict[str, float] | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/extracted-text":
            assert request.url.params["trace"] == "true"
            assert request.headers["X-Debug"] == "sync-json"
            captured_timeout["post"] = request.extensions.get("timeout")
            payload = json.loads(request.content.decode("utf-8"))
            assert payload == payload_dump | {"debug": True}
            return httpx.Response(200, json=expected_response)
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.extract_pdf_text(
            input_file,
            extra_query={"trace": "true"},
            extra_headers={"X-Debug": "sync-json"},
            extra_body={"debug": True},
            timeout=0.25,
        )

    assert isinstance(response, ExtractedTextDocument)
    post_timeout = captured_timeout["post"]
    assert post_timeout is not None
    if isinstance(post_timeout, dict):
        assert all(
            component == pytest.approx(0.25) for component in post_timeout.values()
        )
    else:
        assert post_timeout == pytest.approx(0.25)
    assert response.model_dump(by_alias=True, exclude_none=True) == expected_response


@pytest.mark.asyncio
@pytest.mark.parametrize("options", EXTRACT_TEXT_OPTION_SETS)
@pytest.mark.parametrize("pages", PAGES_OPTION_SETS)
async def test_async_extract_pdf_text_success(
    options: Mapping[str, bool | str],
    pages: list[str] | None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(2))
    base_payload: dict[str, object] = {
        "files": [input_file],
        "output_type": "json",
    }
    if pages is not None:
        base_payload["pages"] = pages
    payload_input = base_payload | dict(options)
    payload_dump = ExtractTextPayload.model_validate(payload_input).model_dump(
        mode="json",
        by_alias=True,
        exclude_none=True,
        exclude_unset=True,
    )
    expected_response = _make_extracted_text_document_payload(str(input_file.id))
    seen: dict[str, int] = {"post": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/extracted-text":
            seen["post"] += 1
            payload = json.loads(request.content.decode("utf-8"))
            assert payload == payload_dump
            return httpx.Response(200, json=expected_response)
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    async with AsyncPdfRestClient(
        api_key=ASYNC_API_KEY,
        transport=transport,
    ) as client:
        request_kwargs: dict[str, object] = {
            "full_text": options["full_text"],
            "preserve_line_breaks": options["preserve_line_breaks"],
            "word_style": options["word_style"],
            "word_coordinates": options["word_coordinates"],
        }
        if pages is not None:
            request_kwargs["pages"] = pages

        response = await client.extract_pdf_text(input_file, **request_kwargs)

    assert seen == {"post": 1}
    assert isinstance(response, ExtractedTextDocument)
    assert response.input_id == input_file.id
    assert response.model_dump(by_alias=True, exclude_none=True) == expected_response


def test_extract_pdf_text_multi_file_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    files = [
        make_pdf_file(PdfRestFileID.generate(1)),
        make_pdf_file(PdfRestFileID.generate(2)),
    ]
    transport = httpx.MockTransport(lambda request: httpx.Response(500))
    with (
        PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client,
        pytest.raises(ValidationError, match="at most 1 item"),
    ):
        client.extract_pdf_text(files)


def test_extract_pdf_text_invalid_pages(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(1))
    transport = httpx.MockTransport(lambda request: httpx.Response(500))
    with (
        PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client,
        pytest.raises(
            ValidationError,
            match="The start page must be less than or equal to the end",
        ),
    ):
        client.extract_pdf_text(input_file, pages=["5-1"])


def test_extract_pdf_text_server_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(1))

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/extracted-text":
            return httpx.Response(400, json={"message": "Invalid option"})
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    with (
        PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client,
        pytest.raises(PdfRestApiError, match="Invalid option"),
    ):
        client.extract_pdf_text(input_file, full_text="off")


@pytest.mark.parametrize(
    ("invalid_kwargs", "match"),
    [
        pytest.param({"full_text": "pages"}, "full_text", id="bad-full-text"),
        pytest.param(
            {"preserve_line_breaks": "maybe"},
            "preserve_line_breaks",
            id="bad-preserve-line-breaks",
        ),
        pytest.param({"word_style": "maybe"}, "word_style", id="bad-word-style"),
        pytest.param(
            {"word_coordinates": "maybe"}, "word_coordinates", id="bad-word-coordinates"
        ),
    ],
)
def test_extract_pdf_text_invalid_option_values(
    invalid_kwargs: Mapping[str, object],
    match: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(1))
    transport = httpx.MockTransport(lambda request: httpx.Response(500))
    with (
        PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client,
        pytest.raises(ValidationError, match=match),
    ):
        client.extract_pdf_text(input_file, **invalid_kwargs)
