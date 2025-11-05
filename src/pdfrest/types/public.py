"""Public type definitions for the pdfrest client."""

from __future__ import annotations

from typing import Literal, cast, get_args

__all__ = ("ALL_PDF_INFO_QUERIES", "PdfInfoQuery")

PdfInfoQuery = Literal[
    "tagged",
    "image_only",
    "title",
    "subject",
    "author",
    "producer",
    "creator",
    "creation_date",
    "modified_date",
    "keywords",
    "custom_metadata",
    "doc_language",
    "page_count",
    "contains_annotations",
    "contains_signature",
    "pdf_version",
    "file_size",
    "filename",
    "restrict_permissions_set",
    "contains_xfa",
    "contains_acroforms",
    "contains_javascript",
    "contains_transparency",
    "contains_embedded_file",
    "uses_embedded_fonts",
    "uses_nonembedded_fonts",
    "pdfa",
    "pdfua_claim",
    "pdfe_claim",
    "pdfx_claim",
    "requires_password_to_open",
]

ALL_PDF_INFO_QUERIES: tuple[PdfInfoQuery, ...] = cast(
    tuple[PdfInfoQuery, ...], get_args(PdfInfoQuery)
)
