"""Pydantic models for pdfrest API payloads."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field

__all__ = ("UpResponse",)


class UpResponse(BaseModel):
    """Response payload returned by the `/up` health endpoint."""

    status: str
    product: str
    release_date: date = Field(alias="releaseDate")
    version: str

    model_config = ConfigDict(populate_by_name=True, frozen=True)


class PdfRestErrorResponse(BaseModel):
    """Error response payloads from pdfRest."""

    error: str | None = Field(alias="message")
    model_config = ConfigDict(extra="allow", frozen=True)
