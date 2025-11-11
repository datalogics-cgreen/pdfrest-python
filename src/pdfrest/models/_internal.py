from __future__ import annotations

import json
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
    model_serializer,
    model_validator,
)

from pdfrest.types.public import PdfRedactionPreset

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


def _split_comma_list(value: Any) -> Any:
    if isinstance(value, str):
        return value.split(",")
    if isinstance(value, list):
        return value
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return list(value)
    msg = "Must be a comma separated string or a list of strings."
    raise ValueError(msg)


def _split_comma_string(value: Any) -> list[Any] | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value.split(",")
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, str)):
        return list(value)
    msg = "Must be a list, or a comma separated string."
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
    return ",".join(str(element) for element in value)


def _serialize_page_ranges(value: list[str | int | tuple[str | int, ...]]) -> str:
    def join_tuple(value: str | int | tuple[str | int, ...]) -> str:
        if isinstance(value, tuple):
            return "-".join(str(e) for e in value)
        return str(value)

    return ",".join(join_tuple(v) for v in value)


def _serialize_grouped_page_ranges(
    value: list[list[str | int | tuple[str | int, ...]]],
) -> list[str]:
    return [_serialize_page_ranges(v) for v in value]


def _serialize_redactions(value: list[_PdfRedactionVariant]) -> str:
    payload = [entry.model_dump(mode="json", exclude_none=True) for entry in value]
    return json.dumps(payload, separators=(",", ":"))


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


PageNumber = Annotated[int, Field(ge=1), PlainSerializer(lambda x: str(x))]


def _split_page_range_tuple(x: str) -> tuple[str, str]:
    start, end = x.split("-", maxsplit=1)
    return start, end


def _ascending_page_range(
    range: tuple[int, int | Literal["last"]],
) -> tuple[int, int | Literal["last"]]:
    start, end = range
    if end != "last" and int(start) > int(end):
        msg = "The start page must be less than or equal to the end page."
        raise ValueError(msg)
    return range


_PageRangeTupleWithLast = Annotated[
    tuple[PageNumber, PageNumber]
    | tuple[Literal["last"], PageNumber]
    | tuple[PageNumber, Literal["last"]],
    BeforeValidator(_split_page_range_tuple),
]

SplitMergePageRange = (
    Literal["even", "odd", "last"] | PageNumber | _PageRangeTupleWithLast
)

_AscendingPageRangeTuple = Annotated[
    tuple[PageNumber, PageNumber] | tuple[PageNumber, Literal["last"]],
    BeforeValidator(_split_page_range_tuple),
    AfterValidator(_ascending_page_range),
]

AscendingPageRange = PageNumber | Literal["last"] | _AscendingPageRangeTuple


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
        AfterValidator(
            _allowed_mime_types("application/pdf", error_msg="Must be a PDF file")
        ),
        PlainSerializer(_serialize_as_first_file_id),
    ]
    queries: Annotated[
        list[PdfInfoQuery],
        Field(min_length=1),
        BeforeValidator(_ensure_list),
        BeforeValidator(_split_comma_list),
        PlainSerializer(_serialize_as_comma_separated_string),
    ]


RgbChannel = Annotated[int, Field(ge=0, le=255)]


class PdfLiteralRedactionModel(BaseModel):
    type: Literal["literal"]
    value: Annotated[str, Field(min_length=1)]


class PdfRegexRedactionModel(BaseModel):
    type: Literal["regex"]
    value: Annotated[str, Field(min_length=1)]


class PdfPresetRedactionModel(BaseModel):
    type: Literal["preset"]
    value: PdfRedactionPreset


_PdfRedactionVariant = Annotated[
    PdfLiteralRedactionModel | PdfRegexRedactionModel | PdfPresetRedactionModel,
    Field(discriminator="type"),
]


class PdfRedactionPreviewPayload(BaseModel):
    """Adapt caller options into a pdfRest-compatible redaction preview request."""

    files: Annotated[
        list[PdfRestFile],
        Field(
            min_length=1,
            max_length=1,
            validation_alias=AliasChoices("file", "files"),
            serialization_alias="id",
        ),
        BeforeValidator(_ensure_list),
        AfterValidator(
            _allowed_mime_types("application/pdf", error_msg="Must be a PDF file")
        ),
        PlainSerializer(_serialize_as_first_file_id),
    ]
    redactions: Annotated[
        list[_PdfRedactionVariant],
        Field(min_length=1),
        BeforeValidator(_ensure_list),
        PlainSerializer(_serialize_redactions),
    ]
    output: Annotated[
        str | None,
        Field(serialization_alias="output", min_length=1, default=None),
        AfterValidator(_validate_output_prefix),
    ] = None


class PdfRedactionApplyPayload(BaseModel):
    """Adapt caller options into a pdfRest-compatible redaction application request."""

    files: Annotated[
        list[PdfRestFile],
        Field(
            min_length=1,
            max_length=1,
            validation_alias=AliasChoices("file", "files"),
            serialization_alias="id",
        ),
        BeforeValidator(_ensure_list),
        AfterValidator(
            _allowed_mime_types("application/pdf", error_msg="Must be a PDF file")
        ),
        PlainSerializer(_serialize_as_first_file_id),
    ]
    rgb_color: Annotated[
        tuple[RgbChannel, RgbChannel, RgbChannel] | None,
        Field(serialization_alias="rgb_color", default=None),
        BeforeValidator(_split_comma_string),
        PlainSerializer(_serialize_as_comma_separated_string),
    ] = None
    output: Annotated[
        str | None,
        Field(serialization_alias="output", min_length=1, default=None),
        AfterValidator(_validate_output_prefix),
    ] = None


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
        list[AscendingPageRange] | None,
        Field(serialization_alias="pages", min_length=1, default=None),
        BeforeValidator(_ensure_list),
        BeforeValidator(_split_comma_list),
        BeforeValidator(_int_to_string),
        PlainSerializer(_serialize_page_ranges),
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


_DEFAULT_FULL_DOCUMENT_RANGE: list[str] = ["1-last"]


class PdfSplitPayload(BaseModel):
    """Adapt caller options into a pdfRest-ready split request payload."""

    files: Annotated[
        list[PdfRestFile],
        Field(
            min_length=1,
            max_length=1,
            validation_alias=AliasChoices("file", "files"),
            serialization_alias="id",
        ),
        BeforeValidator(_ensure_list),
        AfterValidator(
            _allowed_mime_types("application/pdf", error_msg="Must be a PDF file")
        ),
        PlainSerializer(_serialize_as_first_file_id),
    ]
    page_groups: Annotated[
        list[
            Annotated[
                list[SplitMergePageRange],
                BeforeValidator(_ensure_list),
                BeforeValidator(_split_comma_string),
            ]
        ]
        | None,
        Field(
            default=None,
            validation_alias=AliasChoices("pages", "page_groups"),
            serialization_alias="pages",
            min_length=1,
        ),
        BeforeValidator(_ensure_list),
        BeforeValidator(_int_to_string),
        PlainSerializer(_serialize_grouped_page_ranges),
    ]
    output_prefix: Annotated[
        str | None,
        Field(serialization_alias="output", min_length=1, default=None),
        AfterValidator(_validate_output_prefix),
    ] = None


class _PdfMergeItem(BaseModel):
    file: Annotated[
        PdfRestFile,
        AfterValidator(
            _allowed_mime_types("application/pdf", error_msg="Must be a PDF file")
        ),
    ]
    pages: Annotated[
        list[SplitMergePageRange],
        Field(
            min_length=1,
            default_factory=lambda: list(_DEFAULT_FULL_DOCUMENT_RANGE).copy(),
        ),
        BeforeValidator(_list_of_strings),
        BeforeValidator(_ensure_list),
        PlainSerializer(_serialize_page_ranges),
    ]

    @model_validator(mode="before")
    @classmethod
    def _transform_input(cls, data: Any) -> Any:
        if isinstance(data, tuple):
            if len(data) != 2:
                msg = (
                    "Tuple merge entries must contain exactly two items: (file, pages)."
                )
                raise ValueError(msg)
            file_candidate, pages = data
            return {"file": file_candidate, "pages": pages}
        if isinstance(data, PdfRestFile):
            return {"file": data}
        return data


class PdfMergePayload(BaseModel):
    """Adapt caller options into a pdfRest-ready merge request payload."""

    sources: Annotated[
        list[_PdfMergeItem],
        Field(
            min_length=2,
            validation_alias=AliasChoices("sources", "documents", "files"),
        ),
        BeforeValidator(_ensure_list),
    ]
    output_prefix: Annotated[
        str | None,
        Field(serialization_alias="output", min_length=1, default=None),
        AfterValidator(_validate_output_prefix),
    ] = None

    @model_serializer(mode="wrap")
    def _serialize_pdf_merge_payload(
        self, handler: Callable[[PdfMergePayload], dict[str, Any]]
    ) -> dict[str, Any]:
        # Invoke all the serializers on the payload, which then properly serializes
        # all the fields.
        payload = handler(self)
        # Reorganize the serialized data into the parallel arrays that pdfRest expects
        payload["type"] = ["id"] * len(self.sources)
        payload["pages"] = [
            source.get("pages", _DEFAULT_FULL_DOCUMENT_RANGE[0])
            for source in payload["sources"]
        ]
        payload["id"] = [source["file"]["id"] for source in payload["sources"]]
        del payload["sources"]
        return payload


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
