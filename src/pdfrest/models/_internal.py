from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from pathlib import PurePath
from typing import Annotated, Any, Generic, Literal, TypeVar

from pydantic import (
    AfterValidator,
    AliasChoices,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    HttpUrl,
    PlainSerializer,
    model_validator,
)

from ..types import PdfInfoQuery
from . import PdfRestFile
from .public import PdfRestFileID


def _ensure_list(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, list):
        return value
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return list(value)
    return [value]


def _list_of_strings(value: list[Any]) -> list[str]:
    return [str(e) for e in value]


def _validate_output_prefix(value: str | None) -> str | None:
    """Validate output prefix to prevent directory traversal and reserved or unsafe names."""
    if value is None:
        return None
    if "/" in value or "\\" in value or ":" in value:
        msg = "The output prefix must not contain a directory separator."
        raise ValueError(msg)
    if value.startswith("."):
        msg = "The output prefix must not start with a `.`."
        raise ValueError(msg)
    if ".." in value:
        msg = "The output prefix must not contain `..`."
        raise ValueError(msg)
    basename = PurePath(value).name
    if value != basename:
        msg = "The output prefix must not include directory components."
        raise ValueError(msg)
    if basename in {"profile.json", "metadata.json"}:
        msg = "The output prefix is a reserved name."
        raise ValueError(msg)
    special_chars_pattern = r"[`!@#$%^&*()+=\[\]{};':\"\\|,<>?~]"
    matches = re.findall(special_chars_pattern, value)
    if matches:
        violations: list[str] = []
        for char in matches:
            if char not in violations:
                violations.append(char)
        msg = (
            "The output prefix must not contain special characters: "
            + ", ".join(repr(char) for char in violations)
            + "."
        )
        raise ValueError(msg)
    return value


def _require_positive_page(
    text: str, *, description: str, require_page_word: bool = False
) -> str:
    if not text.isdigit() or int(text) < 1:
        message = (
            f"{description} must be a page number greater than or equal to 1."
            if require_page_word
            else f"{description} must be greater than or equal to 1."
        )
        raise ValueError(message)
    return text


def _validate_page_range_entry(value: str) -> str:
    """Normalize and validate a single page range entry."""
    if not isinstance(value, str):
        msg = "Each page range entry must be a string."
        raise TypeError(msg)
    entry = value.strip()
    if entry == "":
        msg = "Each page range entry must be a non-empty string."
        raise ValueError(msg)
    if entry == "last":
        return entry
    if entry.isdigit():
        return _require_positive_page(entry, description="Page numbers")
    if "-" in entry:
        start_raw, end_raw = (part.strip() for part in entry.split("-", maxsplit=1))
        start = _require_positive_page(
            start_raw, description="Page range start", require_page_word=True
        )
        if end_raw == "last":
            return f"{start}-last"
        end = _require_positive_page(
            end_raw, description="Page range end", require_page_word=True
        )
        if int(end) < int(start):
            msg = "Page range end must be greater than or equal to the start."
            raise ValueError(msg)
        return f"{start}-{end}"
    msg = "Page range entries must be positive integers, 'last', or a range like '1-3' or '6-last'."
    raise ValueError(msg)


def _split_comma_list(value: Any) -> Any:
    if isinstance(value, str):
        return value.split(",")
    if isinstance(value, list):
        return value
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return list(value)
    msg = "Must be a comma separated string or a list of strings."
    raise ValueError(msg)


def _pdfrest_file_to_id(value: Any) -> Any:
    if isinstance(value, PdfRestFile):
        return value.id
    return value


def _serialize_as_first_file_id(value: list[PdfRestFile]) -> str:
    return str(value[0].id)


def _serialize_as_comma_separated_string(value: list[Any] | None) -> str | None:
    if value is None:
        return None
    return ",".join(value)


PageRangeEntry = Annotated[str, AfterValidator(_validate_page_range_entry)]


def _allowed_mime_types(
    allowed_mime_types: str, *more_allowed_mime_types: str, error_msg: str | None
) -> Callable[[Any], Any]:
    combined_allowed_mime_types = [allowed_mime_types, *more_allowed_mime_types]

    def allowed_mime_types_validator(
        value: PdfRestFile | list[PdfRestFile],
    ) -> PdfRestFile | list[PdfRestFile]:
        if isinstance(value, list):
            for item in value:
                allowed_mime_types_validator(item)
            return value
        if value.type not in combined_allowed_mime_types:
            msg = error_msg or f"The file type must be one of: {allowed_mime_types}"
            raise ValueError(msg)
        return value

    return allowed_mime_types_validator


def _int_to_string(value: Any) -> Any:
    if isinstance(value, int):
        return str(value)
    if isinstance(value, list):
        return [_int_to_string(item) for item in value]
    return value


class UploadURLs(BaseModel):
    url: Annotated[
        list[HttpUrl] | HttpUrl,
        Field(min_length=1),
        BeforeValidator(_list_of_strings),
        BeforeValidator(_ensure_list),
    ]


class PdfInfoPayload(BaseModel):
    """Adapt caller options into a pdfRest-ready pdf-info request payload."""

    files: Annotated[
        list[PdfRestFile],
        Field(
            min_length=1,
            max_length=1,
            validation_alias=AliasChoices("file", "files"),
            serialization_alias="id",
        ),
        BeforeValidator(_ensure_list),
        PlainSerializer(_serialize_as_first_file_id),
    ]
    queries: Annotated[
        list[PdfInfoQuery],
        Field(min_length=1),
        BeforeValidator(_ensure_list),
        BeforeValidator(_split_comma_list),
        PlainSerializer(_serialize_as_comma_separated_string),
    ]


ColorModelT = TypeVar("ColorModelT", bound=str)


class BasePdfRestGraphicPayload(BaseModel, Generic[ColorModelT]):
    files: Annotated[
        list[PdfRestFile],
        Field(
            min_length=1,
            max_length=1,
            validation_alias=AliasChoices("file", "files"),
            serialization_alias="id",
        ),
        AfterValidator(
            _allowed_mime_types("application/pdf", error_msg="Must be a PDF file")
        ),
        BeforeValidator(_ensure_list),
        PlainSerializer(_serialize_as_first_file_id),
    ]
    output_prefix: Annotated[
        str | None,
        Field(serialization_alias="output", min_length=1, default=None),
        AfterValidator(_validate_output_prefix),
    ]
    page_range: Annotated[
        list[PageRangeEntry] | None,
        Field(serialization_alias="pages", min_length=1, default=None),
        BeforeValidator(_ensure_list),
        BeforeValidator(_split_comma_list),
        BeforeValidator(_int_to_string),
        PlainSerializer(_serialize_as_comma_separated_string),
    ]
    resolution: Annotated[int, Field(ge=12, le=2400, default=300)]
    color_model: Annotated[ColorModelT, Field(default=...)]
    smoothing: Annotated[
        list[Literal["none", "all", "text", "line", "image"]],
        Field(default="none"),
        BeforeValidator(_ensure_list),
        BeforeValidator(_split_comma_list),
        PlainSerializer(_serialize_as_comma_separated_string),
    ]


class PngPdfRestPayload(BasePdfRestGraphicPayload[Literal["rgb", "rgba", "gray"]]):
    """Adapt caller options into a pdfRest-ready PNG request payload."""

    color_model: Annotated[Literal["rgb", "rgba", "gray"], Field(default="rgb")]


class BmpPdfRestPayload(BasePdfRestGraphicPayload[Literal["rgb", "gray"]]):
    """Adapt caller options into a pdfRest-ready BMP request payload."""

    color_model: Annotated[Literal["rgb", "gray"], Field(default="rgb")]


class GifPdfRestPayload(BasePdfRestGraphicPayload[Literal["rgb", "gray"]]):
    """Adapt caller options into a pdfRest-ready GIF request payload."""

    color_model: Annotated[Literal["rgb", "gray"], Field(default="rgb")]


class JpegPdfRestPayload(BasePdfRestGraphicPayload[Literal["rgb", "cmyk", "gray"]]):
    """Adapt caller options into a pdfRest-ready JPEG request payload."""

    color_model: Annotated[Literal["rgb", "cmyk", "gray"], Field(default="rgb")]
    jpeg_quality: Annotated[int, Field(ge=1, le=100, default=75)]


class TiffPdfRestPayload(
    BasePdfRestGraphicPayload[Literal["rgb", "rgba", "cmyk", "lab", "gray"]]
):
    """Adapt caller options into a pdfRest-ready TIFF request payload."""

    color_model: Annotated[
        Literal["rgb", "rgba", "cmyk", "lab", "gray"], Field(default="rgb")
    ]


class PdfRestRawUploadedFile(BaseModel):
    """The response sent by /upload is a list of these. /unzip returns files like this
    with outputUrl"""

    name: Annotated[str, Field(description="The name of the file")]
    id: Annotated[PdfRestFileID, Field(description="The id of the file")]
    output_url: Annotated[
        str | None,
        Field(description="The url of the unzipped file", alias="outputUrl"),
        BeforeValidator(_ensure_list),
    ] = None


class PdfRestRawFileResponse(BaseModel):
    """The raw response from file-based pdfRest calls."""

    # Allow all extra fields to be stored and serialized
    # See: https://docs.pydantic.dev/latest/concepts/models/#extra-fields
    model_config = ConfigDict(extra="allow")

    input_id: Annotated[
        list[PdfRestFileID],
        Field(alias="inputId", description="The id of the input file"),
        BeforeValidator(_ensure_list),
    ]
    output_urls: Annotated[
        list[HttpUrl] | None,
        Field(alias="outputUrl", description="The url of the file"),
        BeforeValidator(_ensure_list),
    ] = None
    output_ids: Annotated[
        list[PdfRestFileID] | None,
        Field(alias="outputId", description="The id of the file"),
        BeforeValidator(_ensure_list),
    ] = None
    files: Annotated[
        list[PdfRestRawUploadedFile] | None,
        Field(description="The file(s) returned from the /unzip operation"),
        BeforeValidator(_ensure_list),
    ] = None
    warning: Annotated[
        str | None,
        Field(
            description="A warning that was generated during the pdfRest operation",
        ),
    ] = None

    @model_validator(mode="after")
    def _check_output_id_or_files(self) -> Any:
        if self.output_ids is None and self.files is None:
            msg = "output_id or files must be specified"
            raise ValueError(msg)
        return self

    @property
    def ids(self) -> list[PdfRestFileID] | None:
        if self.output_ids is not None:
            return self.output_ids
        if self.files is not None:
            return [f.id for f in self.files]
        return None
