from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Any

from pdfrest.models import PdfRestFile

VALID_API_KEY = "12345678-1234-1234-1234-123456789abc"
ASYNC_API_KEY = "fedcba98-7654-3210-fedc-ba9876543210"


def build_file_info_payload(file_id: str, name: str, mime_type: str) -> dict[str, Any]:
    return {
        "id": file_id,
        "name": name,
        "url": f"https://api.pdfrest.com/resource/{file_id}",
        "type": mime_type,
        "size": 256,
        "modified": datetime(2024, 1, 1, tzinfo=timezone.utc)
        .isoformat()
        .replace("+00:00", "Z"),
        "scheduledDeletionTimeUtc": None,
    }


def make_pdf_file(file_id: str, name: str = "example.pdf") -> PdfRestFile:
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


def make_image_file(
    file_id: str,
    mime_type: str = "image/png",
    name: str = "example.png",
) -> PdfRestFile:
    return PdfRestFile.model_validate(
        {
            "id": file_id,
            "name": name,
            "url": f"https://api.pdfrest.com/resource/{file_id}",
            "type": mime_type,
            "size": 2048,
            "modified": datetime(2024, 1, 1, tzinfo=timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
            "scheduledDeletionTimeUtc": None,
        }
    )


def assert_conversion_payload(
    payload: dict[str, Any],
    expected: dict[str, Any],
    *,
    allowed_extras: Iterable[str] | None = None,
) -> None:
    for key, value in expected.items():
        assert payload[key] == value
    extra_keys = set(payload) - set(expected)
    permitted = {"color_model", "resolution", "smoothing"}
    if allowed_extras is not None:
        permitted.update(allowed_extras)
    assert extra_keys <= permitted
    if "resolution" not in expected and "resolution" in payload:
        assert payload["resolution"] == 300
    if "color_model" not in expected and "color_model" in payload:
        assert payload["color_model"] == "rgb"
    if "smoothing" not in expected and "smoothing" in payload:
        assert payload["smoothing"] == "none"
