from __future__ import annotations

import logging
import re
from typing import Any

from pydantic import ValidationInfo

LOGGER = logging.getLogger("pdfrest.models")

_DEMO_UUID = "00000000-0000-4000-8000-000000000000"
_REDACTED_X_PATTERN = re.compile(r"^[Xx-]{8,}$")


def _field_name(info: ValidationInfo) -> str:
    return info.field_name or "<unknown>"


def _looks_like_demo_redaction(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    if _looks_like_generate_redacted_string(value):
        return True
    return bool(_REDACTED_X_PATTERN.fullmatch(value))


def _looks_like_generate_redacted_string(value: str) -> bool:
    """Detect strings redacted by PDFCloud-API generateRedactedString.

    The upstream redactor preserves the first two characters and replaces all
    non-whitespace characters after that with '*'.
    """
    if len(value) < 3:
        return False
    tail = value[2:]
    if "*" not in tail:
        return False
    return all(char == "*" or char.isspace() for char in tail)


def _log_replacement(original: Any, replacement: Any, info: ValidationInfo) -> None:
    LOGGER.warning(
        "Demo value %s detected in %s; replaced with %s",
        original,
        _field_name(info),
        replacement,
    )


def _demo_bool_or_passthrough(
    value: Any, info: ValidationInfo, *, replacement: bool
) -> Any:
    if value is None or isinstance(value, bool):
        return value
    if _looks_like_demo_redaction(value):
        _log_replacement(value, replacement, info)
        return replacement
    return value


def demo_bool_false_or_passthrough(value: Any, info: ValidationInfo) -> Any:
    return _demo_bool_or_passthrough(value, info, replacement=False)


def demo_bool_true_or_passthrough(value: Any, info: ValidationInfo) -> Any:
    return _demo_bool_or_passthrough(value, info, replacement=True)


def demo_file_id_or_passthrough(value: Any, info: ValidationInfo) -> Any:
    if value is None:
        return value
    if _looks_like_demo_redaction(value):
        replacement = _DEMO_UUID
        _log_replacement(value, replacement, info)
        return replacement
    return value


def demo_int_or_passthrough(value: Any, info: ValidationInfo) -> Any:
    if value is None or isinstance(value, int):
        return value
    if _looks_like_demo_redaction(value):
        replacement = 0
        _log_replacement(value, replacement, info)
        return replacement
    return value
