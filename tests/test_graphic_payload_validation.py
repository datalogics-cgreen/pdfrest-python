from __future__ import annotations

import re
from typing import Any

import pytest
from pydantic import ValidationError

from pdfrest.models._internal import (
    BasePdfRestGraphicPayload,
    BmpPdfRestPayload,
    GifPdfRestPayload,
    JpegPdfRestPayload,
    PngPdfRestPayload,
    TiffPdfRestPayload,
)

from .graphics_test_helpers import make_pdf_file

PAYLOAD_MODELS: tuple[type[BasePdfRestGraphicPayload[Any]], ...] = (
    PngPdfRestPayload,
    BmpPdfRestPayload,
    GifPdfRestPayload,
    JpegPdfRestPayload,
    TiffPdfRestPayload,
)


@pytest.mark.parametrize("payload_model", PAYLOAD_MODELS)
def test_graphic_payload_accepts_page_range_variants(
    payload_model: type[BasePdfRestGraphicPayload[Any]],
) -> None:
    payload = payload_model.model_validate(
        {
            "files": [make_pdf_file("12345678-1234-4abc-8def-1234567890ab")],
            "page_range": [1, "last", "6-last"],
        }
    )

    data = payload.model_dump(mode="json", by_alias=True, exclude_none=True)
    assert data["pages"] == "1,last,6-last"


@pytest.mark.parametrize("payload_model", PAYLOAD_MODELS)
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
def test_graphic_payload_invalid_output_prefix(
    payload_model: type[BasePdfRestGraphicPayload[Any]],
    bad_prefix: str,
    expected: str,
) -> None:
    with pytest.raises(ValidationError, match=re.escape(expected)):
        payload_model.model_validate(
            {
                "files": [make_pdf_file("12345678-1234-4abc-8def-1234567890ab")],
                "output_prefix": bad_prefix,
            }
        )


@pytest.mark.parametrize("payload_model", PAYLOAD_MODELS)
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
def test_graphic_payload_invalid_page_range_value(
    payload_model: type[BasePdfRestGraphicPayload[Any]],
    bad_page_range: object,
    expected: str,
) -> None:
    with pytest.raises(ValidationError, match=re.escape(expected)):
        payload_model.model_validate(
            {
                "files": [make_pdf_file("12345678-1234-4abc-8def-1234567890ab")],
                "page_range": bad_page_range,
            }
        )
