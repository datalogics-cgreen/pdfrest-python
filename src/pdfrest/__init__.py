"""Top-level package for the pdfrest client library."""

from importlib import metadata

from .client import AsyncPdfRestClient, PdfRestClient, RequestOptions, UpRequestOptions
from .exceptions import (
    PdfRestApiError,
    PdfRestConfigurationError,
    PdfRestError,
    PdfRestRequestError,
    PdfRestTimeoutError,
    PdfRestTransportError,
    translate_httpx_error,
)
from .models import UpResponse

__all__ = (
    "AsyncPdfRestClient",
    "PdfRestApiError",
    "PdfRestClient",
    "PdfRestConfigurationError",
    "PdfRestError",
    "PdfRestRequestError",
    "PdfRestTimeoutError",
    "PdfRestTransportError",
    "RequestOptions",
    "UpRequestOptions",
    "UpResponse",
    "__version__",
    "translate_httpx_error",
)

try:  # pragma: no cover - fallback should never run in production builds
    __version__ = metadata.version("pdfrest")
except metadata.PackageNotFoundError:  # pragma: no cover
    __version__ = "0.0.0"
