from __future__ import annotations

from typing import Annotated, Any

from pydantic import (
    BaseModel,
    BeforeValidator,
    Field,
    HttpUrl,
)


def _ensure_list(value: Any) -> Any:
    if value is None:
        return None
    if not isinstance(value, list):
        return [value]
    return value


def _list_of_strings(value: list[Any]) -> list[str]:
    return [str(e) for e in value]


class UploadURLs(BaseModel):
    url: Annotated[
        list[HttpUrl] | HttpUrl,
        Field(min_length=1),
        BeforeValidator(_list_of_strings),
        BeforeValidator(_ensure_list),
    ]
