"""Public type definitions for the pdfrest client."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, Literal, cast, get_args

from typing_extensions import Required, TypedDict

if TYPE_CHECKING:
    from pdfrest.models import PdfRestFile
else:  # pragma: no cover - used only for typing at runtime
    PdfRestFile = Any

__all__ = (
    "ALL_OCR_LANGUAGES",
    "ALL_PDF_INFO_QUERIES",
    "ALL_PDF_RESTRICTIONS",
    "BmpColorModel",
    "CompressionLevel",
    "ExportDataFormat",
    "ExtractTextGranularity",
    "FlattenQuality",
    "GifColorModel",
    "GraphicSmoothing",
    "HtmlPageOrientation",
    "HtmlPageSize",
    "HtmlWebLayout",
    "JpegColorModel",
    "OcrLanguage",
    "PdfAType",
    "PdfAddTextObject",
    "PdfCMYKColor",
    "PdfColorProfile",
    "PdfConversionCompression",
    "PdfConversionDownsample",
    "PdfConversionLocale",
    "PdfCustomPageSize",
    "PdfInfoQuery",
    "PdfMergeInput",
    "PdfMergeSource",
    "PdfPageOrientation",
    "PdfPageSelection",
    "PdfPageSize",
    "PdfPresetColorProfile",
    "PdfRGBColor",
    "PdfRedactionInstruction",
    "PdfRedactionPreset",
    "PdfRedactionType",
    "PdfRestriction",
    "PdfSignatureConfiguration",
    "PdfSignatureCredentials",
    "PdfSignatureDisplay",
    "PdfSignatureLocation",
    "PdfTextColor",
    "PdfXType",
    "PngColorModel",
    "SummaryFormat",
    "SummaryOutputFormat",
    "SummaryOutputType",
    "TiffColorModel",
    "TranslateOutputFormat",
    "WatermarkHorizontalAlignment",
    "WatermarkVerticalAlignment",
)

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

PdfRedactionType = Literal["literal", "regex", "preset"]

PdfRedactionPreset = Literal[
    "email",
    "phone_number",
    "date",
    "us_ssn",
    "url",
    "credit_card",
    "credit_debit_pin",
    "bank_routing_number",
    "international_bank_account_number",
    "swift_bic_number",
    "ipv4",
    "ipv6",
]


class PdfRedactionInstruction(TypedDict):
    type: PdfRedactionType
    value: PdfRedactionPreset | str


PdfCMYKColor = tuple[int, int, int, int]
PdfRGBColor = tuple[int, int, int]
PdfTextColor = PdfRGBColor | PdfCMYKColor


class PdfAddTextObject(TypedDict, total=False):
    font: Required[str]
    max_width: Required[float]
    opacity: Required[float]
    page: Required[Literal["all"] | int]
    rotation: Required[float]
    text: Required[str]
    text_color_rgb: PdfRGBColor
    text_color_cmyk: PdfCMYKColor
    text_size: Required[float]
    x: Required[float]
    y: Required[float]
    is_right_to_left: bool


class PdfCustomPageSize(TypedDict):
    custom_height: Required[float]
    custom_width: Required[float]


PdfPageSelection = str | int | Sequence[str | int]


class PdfMergeSource(TypedDict, total=False):
    file: Required[PdfRestFile]
    pages: PdfPageSelection | None


PdfMergeInput = PdfRestFile | PdfMergeSource | tuple[PdfRestFile, PdfPageSelection]

PdfConversionCompression = Literal["lossy", "lossless"]
PdfConversionDownsample = Literal["off", 75, 150, 300, 600, 1200]
PdfConversionLocale = Literal["US", "Germany"]
HtmlPageSize = Literal["letter", "legal", "ledger", "A3", "A4", "A5"]
HtmlPageOrientation = Literal["portrait", "landscape"]
HtmlWebLayout = Literal["desktop", "tablet", "mobile"]


class PdfSignaturePoint(TypedDict):
    x: str | int | float
    y: str | int | float


class PdfSignatureLocation(TypedDict):
    bottom_left: Required[PdfSignaturePoint]
    top_right: Required[PdfSignaturePoint]
    page: Required[str | int]


class PdfSignatureDisplay(TypedDict, total=False):
    include_distinguished_name: bool
    include_datetime: bool
    contact: str
    location: str
    name: str
    reason: str


class PdfNewSignatureConfiguration(TypedDict, total=False):
    type: Required[Literal["new"]]
    location: Required[PdfSignatureLocation]
    name: str
    logo_opacity: float
    display: PdfSignatureDisplay


class PdfExistingSignatureConfiguration(TypedDict, total=False):
    type: Required[Literal["existing"]]
    location: PdfSignatureLocation
    name: str
    logo_opacity: float
    display: PdfSignatureDisplay


PdfSignatureConfiguration = (
    PdfNewSignatureConfiguration | PdfExistingSignatureConfiguration
)


class PdfPfxCredentials(TypedDict):
    pfx: Required[PdfRestFile]
    passphrase: Required[PdfRestFile]


class PdfPemCredentials(TypedDict):
    certificate: Required[PdfRestFile]
    private_key: Required[PdfRestFile]


PdfSignatureCredentials = PdfPfxCredentials | PdfPemCredentials

PdfAType = Literal["PDF/A-1b", "PDF/A-2b", "PDF/A-2u", "PDF/A-3b", "PDF/A-3u"]
PdfXType = Literal["PDF/X-1a", "PDF/X-3", "PDF/X-4", "PDF/X-6"]
ExtractTextGranularity = Literal["off", "by_page", "document"]
CompressionLevel = Literal["low", "medium", "high", "custom"]
FlattenQuality = Literal["low", "medium", "high"]
PngColorModel = Literal["rgb", "rgba", "gray"]
BmpColorModel = Literal["rgb", "gray"]
GifColorModel = Literal["rgb", "gray"]
JpegColorModel = Literal["rgb", "cmyk", "gray"]
TiffColorModel = Literal["rgb", "rgba", "cmyk", "lab", "gray"]
GraphicSmoothing = Literal["none", "all", "text", "line", "image"]
# Server accepts all values here, but enforces form-type subsets at runtime:
# AcroForm -> xfdf/fdf/xml, XFA -> xfd/xdp/xml.
ExportDataFormat = Literal["fdf", "xfdf", "xml", "xdp", "xfd"]

SummaryFormat = Literal[
    "overview",
    "highlight",
    "abstract",
    "bullet_points",
    "numbered_list",
    "table_of_contents",
    "outline",
    "question_answer",
    "action_items",
]

SummaryOutputFormat = Literal["plaintext", "markdown"]
SummaryOutputType = Literal["json", "file"]

TranslateOutputFormat = Literal["plaintext", "markdown"]

OcrLanguage = Literal[
    "ChineseSimplified",
    "ChineseTraditional",
    "Dutch",
    "English",
    "French",
    "German",
    "Italian",
    "Japanese",
    "Korean",
    "Portuguese",
    "Spanish",
]

ALL_OCR_LANGUAGES: tuple[OcrLanguage, ...] = cast(
    tuple[OcrLanguage, ...], get_args(OcrLanguage)
)

PdfRestriction = Literal[
    "print_low",
    "print_high",
    "edit_document_assembly",
    "edit_fill_and_sign_form_fields",
    "edit_annotations",
    "edit_content",
    "copy_content",
    "accessibility_off",
]

ALL_PDF_RESTRICTIONS: tuple[PdfRestriction, ...] = cast(
    tuple[PdfRestriction, ...], get_args(PdfRestriction)
)

PdfPageSize = Literal["letter", "legal", "ledger", "A3", "A4", "A5"] | PdfCustomPageSize
PdfPageOrientation = Literal["portrait", "landscape"]
PdfPresetColorProfile = Literal[
    "lab-d50",
    "srgb",
    "apple-rgb",
    "color-match-rgb",
    "gamma-18",
    "gamma-22",
    "dot-gain-10",
    "dot-gain-15",
    "dot-gain-20",
    "dot-gain-25",
    "dot-gain-30",
    "monitor-rgb",
    "acrobat5-cmyk",
    "acrobat9-cmyk",
]

PdfColorProfile = PdfPresetColorProfile
WatermarkHorizontalAlignment = Literal["left", "center", "right"]
WatermarkVerticalAlignment = Literal["top", "center", "bottom"]
