"""Top-level package for the pdfrest client library."""

from importlib import metadata

from .client import AsyncPdfRestClient, PdfRestClient
from .exceptions import (
    PdfRestApiError,
    PdfRestAuthenticationError,
    PdfRestConfigurationError,
    PdfRestDeleteError,
    PdfRestError,
    PdfRestErrorGroup,
    PdfRestRequestError,
    PdfRestTimeoutError,
    PdfRestTransportError,
    translate_httpx_error,
)
from .models import UpResponse

__all__ = (
    "AsyncPdfRestClient",
    "PdfRestApiError",
    "PdfRestAuthenticationError",
    "PdfRestClient",
    "PdfRestConfigurationError",
    "PdfRestDeleteError",
    "PdfRestError",
    "PdfRestErrorGroup",
    "PdfRestRequestError",
    "PdfRestTimeoutError",
    "PdfRestTransportError",
    "UpResponse",
    "__version__",
    "translate_httpx_error",
)

try:  # pragma: no cover - fallback should never run in production builds
    __version__ = metadata.version("pdfrest")
except metadata.PackageNotFoundError:  # pragma: no cover
    __version__ = "0.0.0"
