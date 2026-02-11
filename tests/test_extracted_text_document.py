"""Tests for ExtractedTextDocument validation and serialization."""

from __future__ import annotations

import pytest

from pdfrest.models import ExtractedTextDocument


def test_extract_text_document_round_trip_document_mode() -> None:
    data = {
        "inputId": "153ec1a0f-07e4-4f42-bc64-05180f72a06c",
        "fullText": "The lamb walks My Cow Eats!",
    }

    document = ExtractedTextDocument.model_validate(data)

    assert document.input_id == data["inputId"]
    assert document.full_text is not None
    assert document.full_text.document_text == "The lamb walks My Cow Eats!"
    assert document.full_text.iter_pages() == []
    assert document.words is None

    with pytest.raises(
        ValueError,
        match="full text payload was emitted in document mode; page data unavailable",
    ):
        _ = document.full_text.pages

    assert document.model_dump(by_alias=True, exclude_none=True) == data


def test_extract_text_document_round_trip_page_mode() -> None:
    data = {
        "inputId": "10559e808-4073-488b-b660-a0b1106dd98e",
        "words": [
            {
                "text": "The",
                "page": 1,
                "coordinates": {
                    "topLeft": {"x": 72, "y": 720.7918090820312},
                    "topRight": {"x": 90.12725830078125, "y": 720.7918090820312},
                    "bottomLeft": {"x": 72, "y": 704.72412109375},
                    "bottomRight": {"x": 90.12725830078125, "y": 704.72412109375},
                },
                "style": {
                    "color": {"space": "DeviceRGB", "values": [0, 0, 0]},
                    "font": {"name": "Calibri", "size": 12},
                },
            }
        ],
        "fullText": {
            "pages": [
                {"page": 1, "text": "The lamb walks"},
                {"page": 2, "text": "My Cow Eats!"},
            ]
        },
    }

    document = ExtractedTextDocument.model_validate(data)

    assert document.input_id == data["inputId"]
    assert document.full_text is not None
    assert document.words is not None
    assert len(document.words) == 1
    assert document.full_text.document_text == "The lamb walks My Cow Eats!"
    pages = document.full_text.pages
    assert len(pages) == 2
    assert pages[0].page == 1
    assert pages[0].text == "The lamb walks"
    assert pages[1].page == 2
    assert pages[1].text == "My Cow Eats!"
    assert document.full_text.iter_pages() == pages

    word = document.words[0]
    assert word.text == "The"
    assert word.page == 1
    assert word.style is not None
    assert word.style.color.space == "DeviceRGB"
    assert word.style.color.values == [0, 0, 0]
    assert word.style.font.name == "Calibri"
    assert word.style.font.size == 12
    assert word.coordinates is not None
    assert word.coordinates.top_left.x == 72
    assert word.coordinates.top_left.y == 720.7918090820312
    assert word.coordinates.top_right.x == 90.12725830078125
    assert word.coordinates.top_right.y == 720.7918090820312
    assert word.coordinates.bottom_left.x == 72
    assert word.coordinates.bottom_left.y == 704.72412109375
    assert word.coordinates.bottom_right.x == 90.12725830078125
    assert word.coordinates.bottom_right.y == 704.72412109375

    assert document.model_dump(by_alias=True, exclude_none=True) == data


def test_extract_text_document_round_trip_without_words_or_full_text() -> None:
    data = {
        "inputId": "3f59e808-4073-488b-b660-a0b1106dd9aa",
    }

    document = ExtractedTextDocument.model_validate(data)

    assert document.input_id == data["inputId"]
    assert document.full_text is None
    assert document.words is None
    assert document.model_dump(by_alias=True, exclude_none=True) == data


@pytest.mark.parametrize(
    ("word_payload", "has_coordinates", "has_style"),
    [
        pytest.param(
            {"text": "Simple", "page": 1},
            False,
            False,
            id="minimal-word",
        ),
        pytest.param(
            {
                "text": "CoordsOnly",
                "page": 2,
                "coordinates": {
                    "topLeft": {"x": 1, "y": 2},
                    "topRight": {"x": 3, "y": 4},
                    "bottomLeft": {"x": 5, "y": 6},
                    "bottomRight": {"x": 7, "y": 8},
                },
            },
            True,
            False,
            id="coordinates-only",
        ),
        pytest.param(
            {
                "text": "StyleOnly",
                "page": 3,
                "style": {
                    "color": {"space": "DeviceRGB", "values": [0.1, 0.2, 0.3]},
                    "font": {"name": "Calibri", "size": 10},
                },
            },
            False,
            True,
            id="style-only",
        ),
        pytest.param(
            {
                "text": "Both",
                "page": 4,
                "coordinates": {
                    "topLeft": {"x": 10, "y": 11},
                    "topRight": {"x": 12, "y": 13},
                    "bottomLeft": {"x": 14, "y": 15},
                    "bottomRight": {"x": 16, "y": 17},
                },
                "style": {
                    "color": {"space": "DeviceCMYK", "values": [0, 0, 0, 1]},
                    "font": {"name": "Times", "size": 8.5},
                },
            },
            True,
            True,
            id="coordinates-and-style",
        ),
    ],
)
def test_extracted_text_words_optional_fields(
    word_payload: dict[str, object], has_coordinates: bool, has_style: bool
) -> None:
    data = {
        "inputId": "6f59e808-4073-488b-b660-a0b1106dd9bb",
        "words": [word_payload],
    }

    document = ExtractedTextDocument.model_validate(data)

    assert document.input_id == data["inputId"]
    assert document.words is not None
    word = document.words[0]
    assert word.text == word_payload["text"]
    assert word.page == word_payload["page"]

    if has_coordinates:
        assert word.coordinates is not None
        coord_payload = word_payload.get("coordinates")
        assert isinstance(coord_payload, dict)
        top_left = coord_payload["topLeft"]
        top_right = coord_payload["topRight"]
        bottom_left = coord_payload["bottomLeft"]
        bottom_right = coord_payload["bottomRight"]
        assert word.coordinates.top_left.x == top_left["x"]
        assert word.coordinates.top_left.y == top_left["y"]
        assert word.coordinates.top_right.x == top_right["x"]
        assert word.coordinates.top_right.y == top_right["y"]
        assert word.coordinates.bottom_left.x == bottom_left["x"]
        assert word.coordinates.bottom_left.y == bottom_left["y"]
        assert word.coordinates.bottom_right.x == bottom_right["x"]
        assert word.coordinates.bottom_right.y == bottom_right["y"]
        assert word.coordinates.model_dump(by_alias=True) == coord_payload
    else:
        assert word.coordinates is None

    if has_style:
        assert word.style is not None
        style_payload = word_payload.get("style")
        assert isinstance(style_payload, dict)
        color_payload = style_payload["color"]
        font_payload = style_payload["font"]
        assert isinstance(color_payload, dict)
        assert isinstance(font_payload, dict)
        assert word.style.color.space == color_payload["space"]
        assert word.style.color.values == color_payload["values"]
        assert word.style.font.name == font_payload["name"]
        assert word.style.font.size == font_payload["size"]
    else:
        assert word.style is None

    assert document.model_dump(by_alias=True, exclude_none=True) == data


def test_extract_text_document_page_mode_without_words() -> None:
    data = {
        "inputId": "9f59e808-4073-488b-b660-a0b1106dd9cc",
        "fullText": {
            "pages": [
                {"page": 1, "text": "One"},
                {"page": 2, "text": "Two"},
            ]
        },
    }

    document = ExtractedTextDocument.model_validate(data)

    assert document.input_id == data["inputId"]
    assert document.words is None
    assert document.full_text is not None
    pages = document.full_text.pages
    assert len(pages) == 2
    assert pages[0].page == 1
    assert pages[0].text == "One"
    assert pages[1].page == 2
    assert pages[1].text == "Two"
    assert document.full_text.document_text == "One Two"
    assert document.model_dump(by_alias=True, exclude_none=True) == data
