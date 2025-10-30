"""Pydantic models for pdfrest API payloads."""

from __future__ import annotations

from datetime import date

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, HttpUrl

__all__ = ("PdfRestErrorResponse", "PdfRestFile", "UpResponse")


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

    id: str = Field(
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
