"""Pydantic models for pdfrest API payloads."""

from __future__ import annotations

import re
import uuid as _uuid
from datetime import date
from typing import Annotated, Any, ClassVar

from pydantic import (
    AliasChoices,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
)
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import CoreSchema
from typing_extensions import override

__all__ = (
    "ConvertToMarkdownResponse",
    "ExtractTextResponse",
    "PdfRestDeletionResponse",
    "PdfRestErrorResponse",
    "PdfRestFile",
    "PdfRestFileBasedResponse",
    "PdfRestFileID",
    "PdfRestInfoResponse",
    "SummarizePdfTextResponse",
    "TranslatePdfTextResponse",
    "UpResponse",
)


class PdfRestFileID(str):
    """
    A str-like type representing:
      [optional '1' or '2' prefix] + [UUIDv4 with hyphens]

    Examples:
      - "de305d2-b6a0-4b5d-9a55-4e4e6d8c2d39"          # no prefix
      - "1de305d2-b6a0-4b5d-9a55-4e4e6d8c2d39"        # prefix '1'
      - "2DE305D2-B6A0-4B5D-9A55-4E4E6D8C2D39"        # prefix '2' (upper-case input accepted)

    Canonical representation is lowercase.
    """

    __slots__ = ()

    # For Python validation (case-insensitive)
    _PY_PATTERN: ClassVar[re.Pattern[str]] = re.compile(
        r"^(?:[12])?(?:[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12})$",
        re.IGNORECASE,
    )

    # For JSON Schema (no inline flags; must include both cases)
    _PATTERN_STR: ClassVar[str] = (
        r"^(?:[12])?(?:[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-4[0-9A-Fa-f]{3}-[89ABab][0-9A-Fa-f]{3}-[0-9A-Fa-f]{12})$"
    )

    def __new__(cls, value: str) -> PdfRestFileID:
        if not cls._PY_PATTERN.fullmatch(value):
            msg = (
                "Invalid PdfRestPrefixedUUID4. Expected: "
                "optional '1' or '2' prefix + UUIDv4 with hyphens and RFC 4122 variant"
            )
            raise ValueError(msg)
        return str.__new__(cls, value.lower())

    @override
    def __str__(self) -> str:
        return str.__str__(self)

    @override
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({super().__repr__()})"

    @property
    def prefix(self) -> str | None:
        """
        The leading prefix digit ('1' or '2') if present, else None.

        Note: Presence is unambiguous by length:
          - 36 chars => no prefix
          - 37 chars => prefix present
        """
        return self[0] if len(self) == 37 else None

    @property
    def uuid(self) -> str:
        """The UUID part (without the optional prefix)."""
        return self[1:] if len(self) == 37 else self

    @property
    def uuid_obj(self) -> _uuid.UUID:
        """The UUID object for the UUID part."""
        return _uuid.UUID(self.uuid)

    @classmethod
    def is_valid(cls, value: str) -> bool:
        """Quick validity check without constructing the object."""
        return bool(cls._PY_PATTERN.fullmatch(value))

    @classmethod
    def from_parts(
        cls, u: str | _uuid.UUID, prefix: int | str | None = None
    ) -> PdfRestFileID:
        """
        Build from a UUIDv4 (str or uuid.UUID) and an optional prefix (1 or 2).
        Raises ValueError if not a v4 UUID or bad prefix.
        """
        if isinstance(prefix, int):
            prefix = str(prefix)  # allow 1/2 as int
        if prefix not in (None, "1", "2"):
            msg = "prefix must be None, '1', or '2'"
            raise ValueError(msg)

        if isinstance(u, _uuid.UUID):
            if u.version != 4:
                msg = "UUID must be version 4"
                raise ValueError(msg)
            u_text = str(u)
        else:
            u_text = str(u)
            if not re.fullmatch(
                r"[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-4[0-9A-Fa-f]{3}-[89ABab][0-9A-Fa-f]{3}-[0-9A-Fa-f]{12}",
                u_text,
            ):
                msg = "UUID text must be version 4 with RFC 4122 variant"
                raise ValueError(msg)

        return cls((prefix or "") + u_text)

    @classmethod
    def generate(cls, prefix: int | str | None = None) -> PdfRestFileID:
        """Generate a new value with an optional prefix (1 or 2)."""
        if isinstance(prefix, int):
            prefix = str(prefix)
        if prefix not in (None, "1", "2"):
            msg = "prefix must be None, '1', or '2'"
            raise ValueError(msg)
        return cls.from_parts(_uuid.uuid4(), prefix=prefix)

    # -------------------------
    # Pydantic v2 integration
    # -------------------------
    @classmethod
    def __get_pydantic_core_schema__(cls, source_type: Any, handler: Any) -> CoreSchema:
        """
        Build a Pydantic v2 core schema that accepts:
          - a UUID (validated as v4) -> converted to this type (no prefix)
          - a string matching our pattern
        """
        from pydantic_core import core_schema

        str_schema = core_schema.str_schema(pattern=cls._PATTERN_STR)
        uuid_schema = core_schema.uuid_schema(version=4)
        union = core_schema.union_schema([uuid_schema, str_schema])

        def to_class(v: Any) -> PdfRestFileID:
            if isinstance(v, _uuid.UUID):
                # UUID input: no prefix
                return cls(str(v))
            # string already pattern-validated by inner schema
            return cls(v)

        return core_schema.no_info_after_validator_function(
            to_class,
            union,
            serialization=core_schema.to_string_ser_schema(),
        )

    @classmethod
    def __get_pydantic_json_schema__(
        cls, core_schema: Any, handler: Any
    ) -> JsonSchemaValue:
        """
        Provide a clean JSON Schema for OpenAPI/JSON Schema generators.
        """
        # Prefer a single-string schema with pattern and examples
        return {
            "type": "string",
            "title": cls.__name__,
            "description": "UUIDv4 with hyphens, optionally prefixed by '1' or '2'.",
            "pattern": cls._PATTERN_STR,
            "examples": [
                "de305d2-b6a0-4b5d-9a55-4e4e6d8c2d39",
                "1de305d2-b6a0-4b5d-9a55-4e4e6d8c2d39",
            ],
        }


class UpResponse(BaseModel):
    """Response payload returned by the `/up` health endpoint."""

    status: str
    product: str
    release_date: date = Field(alias="releaseDate")
    version: str

    model_config = ConfigDict(frozen=True)


class PdfRestErrorResponse(BaseModel):
    """Error response payloads from pdfRest."""

    error: str | None = Field(alias="message")
    model_config = ConfigDict(extra="allow", frozen=True)


class PdfRestFile(BaseModel):
    """Represents a file on the pdfRest server."""

    id: PdfRestFileID = Field(
        min_length=1,
        description="Identifier of the file on the pdfRest server",
    )
    name: str = Field(
        min_length=1,
        description="Name of the file",
    )
    url: HttpUrl = Field(
        description="URL from which the file can be downloaded",
    )
    type: str = Field(
        min_length=1,
        description="MIME type of the file",
    )
    size: int = Field(
        description="Size of the file",
    )
    modified: AwareDatetime = Field(
        description="The last modified time of the file, which must include time zone "
        "info.",
    )
    scheduled_deletion_time_utc: AwareDatetime | None = Field(
        alias="scheduledDeletionTimeUtc",
        default=None,
        description="The UTC time at which the file will be deleted from the server.",
    )

    model_config = ConfigDict(frozen=True)


class PdfRestFileBasedResponse(BaseModel):
    """
    Represents a response from a pdfRest API operation that is file-based, allowing
    handling of input and output files along with additional warnings.
    """

    # Allow all extra fields to be stored and serialized
    # See: https://docs.pydantic.dev/latest/concepts/models/#extra-fields
    model_config = ConfigDict(extra="allow")

    input_ids: Annotated[
        list[PdfRestFileID],
        Field(
            description="The ids of the files that were input to the pdfRest operation",
            min_length=1,
            validation_alias=AliasChoices("input_id", "inputId"),
        ),
    ]

    # Optional because some endpoints may not make output
    output_files: Annotated[
        list[PdfRestFile],
        Field(
            description="The list of files returned by the pdfRest operation",
            validation_alias=AliasChoices("output_file", "outputFile"),
        ),
    ]

    warning: Annotated[
        str | None,
        Field(
            description="A warning that was generated during the pdfRest operation",
        ),
    ] = None

    @property
    def input_id(self) -> PdfRestFileID:
        if len(self.input_ids) == 1:
            return self.input_ids[0]
        if len(self.input_ids) == 0:
            msg = "no input id was specified"
        else:
            msg = "multiple input ids were specified"
        raise ValueError(msg)

    @property
    def output_file(self) -> PdfRestFile:
        if len(self.output_files) == 1:
            return self.output_files[0]
        if len(self.output_files) == 0:
            msg = "no output file was returned by the pdfRest operation"
        else:
            msg = "multiple output files were returned by the pdfRest operation"
        raise ValueError(msg)


class PdfRestDeletionResponse(BaseModel):
    """Response returned by the delete tool."""

    model_config = ConfigDict(extra="allow")

    deletion_responses: Annotated[
        dict[PdfRestFileID, str],
        Field(
            alias="deletionResponses",
            validation_alias=AliasChoices("deletion_responses", "deletionResponses"),
            description="Mapping of file ids to deletion results.",
            min_length=1,
        ),
    ]


class SummarizePdfTextResponse(BaseModel):
    """Response returned by the summarize-pdf-text tool."""

    model_config = ConfigDict(extra="allow")

    summary: Annotated[
        str | None,
        Field(
            description="Inline summary content when output_type is json.",
            default=None,
        ),
    ] = None
    input_id: Annotated[
        PdfRestFileID,
        Field(
            validation_alias=AliasChoices("input_id", "inputId"),
            description="The id of the input file.",
        ),
    ]
    output_url: Annotated[
        HttpUrl | None,
        Field(
            alias="outputUrl",
            validation_alias=AliasChoices("output_url", "outputUrl"),
            description="Download URL for file output.",
            default=None,
        ),
    ] = None
    output_id: Annotated[
        PdfRestFileID | None,
        Field(
            alias="outputId",
            validation_alias=AliasChoices("output_id", "outputId"),
            description="The id of the generated output when output_type is file.",
            default=None,
        ),
    ] = None


class TranslatePdfTextResponse(BaseModel):
    """Response returned by the translated-pdf-text tool."""

    model_config = ConfigDict(extra="allow")

    translated_text: Annotated[
        str | None,
        Field(
            alias="translated_text",
            validation_alias=AliasChoices("translated_text", "translatedText"),
            description="Inline translation content when output_type is json.",
            default=None,
        ),
    ] = None
    input_id: Annotated[
        PdfRestFileID,
        Field(
            validation_alias=AliasChoices("input_id", "inputId"),
            description="The id of the input file.",
        ),
    ]
    output_url: Annotated[
        HttpUrl | None,
        Field(
            alias="outputUrl",
            validation_alias=AliasChoices("output_url", "outputUrl"),
            description="Download URL for file output.",
            default=None,
        ),
    ] = None
    output_id: Annotated[
        PdfRestFileID | None,
        Field(
            alias="outputId",
            validation_alias=AliasChoices("output_id", "outputId"),
            description="The id of the generated output when output_type is file.",
            default=None,
        ),
    ] = None


class ExtractTextResponse(BaseModel):
    """Response returned by the extracted-text tool."""

    model_config = ConfigDict(extra="allow")

    full_text: Annotated[
        str | None,
        Field(
            alias="fullText",
            validation_alias=AliasChoices("full_text", "fullText"),
            description="Inline extracted text when output_type is json.",
            default=None,
        ),
    ] = None
    input_id: Annotated[
        PdfRestFileID,
        Field(
            validation_alias=AliasChoices("input_id", "inputId"),
            description="The id of the input file.",
        ),
    ]
    output_url: Annotated[
        HttpUrl | None,
        Field(
            alias="outputUrl",
            validation_alias=AliasChoices("output_url", "outputUrl"),
            description="Download URL for file output.",
            default=None,
        ),
    ] = None
    output_id: Annotated[
        PdfRestFileID | None,
        Field(
            alias="outputId",
            validation_alias=AliasChoices("output_id", "outputId"),
            description="The id of the generated output when output_type is file.",
            default=None,
        ),
    ] = None
    warning: Annotated[
        str | None,
        Field(description="A warning that was generated during text extraction."),
    ] = None


class ConvertToMarkdownResponse(BaseModel):
    """Response returned by the markdown conversion tool."""

    model_config = ConfigDict(extra="allow")

    markdown: Annotated[
        str | None,
        Field(
            description="Inline markdown content when output_type is json.",
            default=None,
        ),
    ] = None
    input_id: Annotated[
        PdfRestFileID,
        Field(
            validation_alias=AliasChoices("input_id", "inputId"),
            description="The id of the input file.",
        ),
    ]
    output_url: Annotated[
        HttpUrl | None,
        Field(
            alias="outputUrl",
            validation_alias=AliasChoices("output_url", "outputUrl"),
            description="Download URL for file output.",
            default=None,
        ),
    ] = None
    output_id: Annotated[
        PdfRestFileID | None,
        Field(
            alias="outputId",
            validation_alias=AliasChoices("output_id", "outputId"),
            description="The id of the generated output when output_type is file.",
            default=None,
        ),
    ] = None
    warning: Annotated[
        str | None,
        Field(description="A warning that was generated during markdown conversion."),
    ] = None


class PdfRestInfoResponse(BaseModel):
    """A response containing the output from the /info route."""

    # Allow all extra fields to be stored and serialized
    # See: https://docs.pydantic.dev/latest/concepts/models/#extra-fields
    model_config = ConfigDict(extra="allow")

    input_id: Annotated[
        PdfRestFileID,
        Field(
            validation_alias=AliasChoices("input_id", "inputId"),
            description="The id of the input file",
        ),
    ]
    tagged: Annotated[
        bool | None,
        Field(
            description="Indicates whether structure tags are present in the PDF "
            "document. The result is true or false."
        ),
    ] = None
    image_only: Annotated[
        bool | None,
        Field(
            description=(
                "Indicates whether the document is 'image only,' meaning it consists "
                "solely of embedded graphical images with no text or other standard "
                "PDF document features except for metadata. The result is true or "
                "false."
            )
        ),
    ] = None
    title: Annotated[
        str | None,
        Field(
            description=(
                "The title of the PDF as retrieved from the metadata. The result is a "
                "string that may be empty if the document does not have a title."
            )
        ),
    ] = None
    subject: Annotated[
        str | None,
        Field(
            description=(
                "The subject of the PDF as retrieved from the metadata. The result is "
                "a string that may be empty if the document does not have a subject."
            )
        ),
    ] = None
    author: Annotated[
        str | None,
        Field(
            description=(
                "The author of the PDF as retrieved from the metadata. The result is "
                "a string that may be empty if the document does not have an author."
            )
        ),
    ] = None
    producer: Annotated[
        str | None,
        Field(
            description=(
                "The producer of the PDF as retrieved from the metadata. The result "
                "is a string that may be empty if the document does not have a "
                "producer."
            )
        ),
    ] = None
    creator: Annotated[
        str | None,
        Field(
            description=(
                "The creator of the PDF as retrieved from the metadata. The result is "
                "a string that may be empty if the document does not have a creator."
            )
        ),
    ] = None
    creation_date: Annotated[
        str | None,
        Field(
            description=(
                "The creation date of the PDF as retrieved from the metadata. The "
                "result is a string that may be empty if the document does not "
                "have a creation date."
            )
        ),
    ] = None
    modified_date: Annotated[
        str | None,
        Field(
            description=(
                "The most recent modification date of the PDF as retrieved from the "
                "metadata. The result is a string that may be empty if the document "
                "does not have a modification date."
            )
        ),
    ] = None
    keywords: Annotated[
        str | None,
        Field(
            description=(
                "The keywords of the PDF as retrieved from the metadata. The result "
                "is a string that may be empty if the document does not include "
                "keywords."
            )
        ),
    ] = None
    custom_metadata: Annotated[
        dict[str, Any] | None,
        Field(
            description=(
                "Custom metadata entries extracted from the PDF. The result is a "
                "dictionary mapping keys to their stored values, or None when no "
                "custom metadata exists."
            )
        ),
    ] = None
    doc_language: Annotated[
        str | None,
        Field(
            description="The language of the document as declared in its metadata. "
            "The result is a string."
        ),
    ] = None
    page_count: Annotated[
        int | None,
        Field(
            description="The number of pages in the PDF document. The result is an "
            "integer."
        ),
    ] = None
    contains_annotations: Annotated[
        bool | None,
        Field(
            description=(
                "Indicates whether the PDF document contains annotations such as "
                "notes, highlighted text, file attachments, crossed-out text, or text "
                "callout boxes. The result is true or false."
            )
        ),
    ] = None
    contains_signature: Annotated[
        bool | None,
        Field(
            description="Indicates whether the PDF contains any digital signatures. "
            "The result is true or false."
        ),
    ] = None
    pdf_version: Annotated[
        str | None,
        Field(
            description=(
                "The version of the PDF standard used to create the document. The "
                "result is a string in the format X.Y.Z, where X, Y, and Z represent "
                "the major, minor, and extension versions."
            )
        ),
    ] = None
    file_size: Annotated[
        int | None,
        Field(
            description="The size of the PDF file in bytes. The result is an integer."
        ),
    ] = None
    filename: Annotated[
        str | None,
        Field(description="The name of the PDF file. The result is a string."),
    ] = None
    restrict_permissions_set: Annotated[
        bool | None,
        Field(
            description=(
                "Indicates whether the PDF file has restricted permissions, such as "
                "preventing printing, copying, or signing. The result is true or "
                "false."
            )
        ),
    ] = None
    contains_xfa: Annotated[
        bool | None,
        Field(
            description="Indicates whether the PDF contains XFA forms. The result is "
            "true or false."
        ),
    ] = None
    contains_acroforms: Annotated[
        bool | None,
        Field(
            description="Indicates whether the PDF contains Acroforms. The result is "
            "true or false."
        ),
    ] = None
    contains_javascript: Annotated[
        bool | None,
        Field(
            description="Indicates whether the PDF contains JavaScript. The result is "
            "true or false."
        ),
    ] = None
    contains_transparency: Annotated[
        bool | None,
        Field(
            description="Indicates whether the PDF contains transparent objects. The "
            "result is true or false."
        ),
    ] = None
    contains_embedded_file: Annotated[
        bool | None,
        Field(
            description="Indicates whether the PDF contains one or more embedded "
            "files. The result is true or false."
        ),
    ] = None
    uses_embedded_fonts: Annotated[
        bool | None,
        Field(
            description="Indicates whether the PDF contains fully embedded fonts. "
            "The result is true or false."
        ),
    ] = None
    uses_nonembedded_fonts: Annotated[
        bool | None,
        Field(
            description="Indicates whether the PDF contains non-embedded fonts. The "
            "result is true or false."
        ),
    ] = None
    pdfa: Annotated[
        bool | None,
        Field(
            description="Indicates whether the document conforms to the PDF/A "
            "standard. The result is true or false."
        ),
    ] = None
    pdfua_claim: Annotated[
        bool | None,
        Field(
            description="Indicates whether the document claims to conform to the "
            "PDF/UA standard. The result is true or false."
        ),
    ] = None
    pdfe_claim: Annotated[
        bool | None,
        Field(
            description="Indicates whether the document claims to conform to the "
            "PDF/E standard. The result is true or false."
        ),
    ] = None
    pdfx_claim: Annotated[
        bool | None,
        Field(
            description="Indicates whether the document claims to conform to the "
            "PDF/X standard. The result is true or false."
        ),
    ] = None
    requires_password_to_open: Annotated[
        bool | None,
        Field(
            description=(
                "Indicates whether the PDF requires a password to open. The result "
                "is true or false. *Note*: A document requiring a password cannot be "
                "opened by this route and will not provide much other information."
            )
        ),
    ] = None
    all_queries_processed: Annotated[
        bool,
        Field(
            validation_alias=AliasChoices(
                "all_queries_processed", "allQueriesProcessed"
            ),
            description=(
                "Indicates whether all possible queries about the PDF document were "
                "successfully processed. This field is required, and the result is "
                "true or false."
            ),
        ),
    ]
    warning: Annotated[
        str | None,
        Field(
            description="A warning indicating why not all queries could be processed.",
        ),
    ] = None
