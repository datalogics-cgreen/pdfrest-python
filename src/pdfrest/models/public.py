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
from pydantic_core import CoreSchema

__all__ = ("PdfRestErrorResponse", "PdfRestFile", "PdfRestFileID", "UpResponse")


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
        if not isinstance(value, str):
            msg = "PdfRestPrefixedUUID4 requires a str"
            raise TypeError(msg)
        if not cls._PY_PATTERN.fullmatch(value):
            msg = (
                "Invalid PdfRestPrefixedUUID4. Expected: "
                "optional '1' or '2' prefix + UUIDv4 with hyphens and RFC 4122 variant"
            )
            raise ValueError(msg)
        return str.__new__(cls, value.lower())

    def __str__(self) -> str:
        return str.__str__(self)

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
        return isinstance(value, str) and bool(cls._PY_PATTERN.fullmatch(value))

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
    def __get_pydantic_json_schema__(cls, core_schema: Any, handler: Any) -> dict:
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
            min_length=1,
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
