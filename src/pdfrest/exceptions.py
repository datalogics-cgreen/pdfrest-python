"""Library-specific exception types for the pdfrest client."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

import httpx
from typing_extensions import override

if TYPE_CHECKING:  # pragma: no cover
    from .models import PdfRestFileID

__all__ = (
    "PdfRestApiError",
    "PdfRestAuthenticationError",
    "PdfRestConfigurationError",
    "PdfRestConnectTimeoutError",
    "PdfRestDeleteError",
    "PdfRestError",
    "PdfRestErrorGroup",
    "PdfRestPoolTimeoutError",
    "PdfRestRequestError",
    "PdfRestTimeoutError",
    "PdfRestTransportError",
    "translate_httpx_error",
)

from exceptiongroup import ExceptionGroup


class PdfRestError(Exception):
    """Base exception for all pdfrest client errors."""


class PdfRestConfigurationError(PdfRestError):
    """Raised when the client is misconfigured (for example, missing API key)."""


class PdfRestTimeoutError(PdfRestError):
    """Raised when a request to pdfrest exceeds the configured timeout."""


class PdfRestConnectTimeoutError(PdfRestTimeoutError):
    """Raised when the client cannot establish a connection before timeout."""


class PdfRestPoolTimeoutError(PdfRestTimeoutError):
    """Raised when the connection pool cannot provide a connection in time."""


class PdfRestTransportError(PdfRestError):
    """Raised when a transport-level error occurs while communicating with pdfrest."""


class PdfRestRequestError(PdfRestError):
    """Raised when the request fails before receiving a response."""


class PdfRestApiError(PdfRestError):
    """Raised when the pdfrest API returns a non-successful response."""

    def __init__(
        self,
        status_code: int,
        message: str | None = None,
        response_content: Any | None = None,
        *,
        retry_after: float | None = None,
    ) -> None:
        self.status_code = status_code
        self.response_content = response_content
        self.retry_after = retry_after
        detail = message or f"pdfRest API returned status code {status_code}"
        super().__init__(detail)

    @override
    def __str__(self) -> str:  # pragma: no cover - mirrors Exception.__str__
        base = super().__str__()
        if self.response_content is None:
            return base
        return f"{base}: {self.response_content}"


class PdfRestAuthenticationError(PdfRestApiError):
    """Raised when authentication with the pdfRest API fails."""


class PdfRestDeleteError(PdfRestError):
    """Raised when an individual file cannot be deleted."""

    def __init__(self, file_id: PdfRestFileID | str, message: str) -> None:
        self.file_id = str(file_id)
        self.detail = message
        super().__init__(f"Failed to delete file {self.file_id}: {message}")


class PdfRestErrorGroup(ExceptionGroup):
    """Group of PdfRestError exceptions produced by the PDF REST library."""

    def __init__(self, message: str, exceptions: Sequence[Exception], /) -> None:
        # enforce that everything inside is from your library
        for e in exceptions:
            if not isinstance(e, PdfRestError):
                msg = f"PdfRestErrorGroup may only contain PdfRestError instances, got {type(e)}"
                raise TypeError(msg)
        super().__init__(message, list(exceptions))


def translate_httpx_error(exc: httpx.HTTPError) -> PdfRestError:
    """Convert an httpx exception into a library-specific exception."""
    if isinstance(exc, httpx.ConnectTimeout):
        return PdfRestConnectTimeoutError(
            str(exc) or "Connection timed out while calling pdfRest."
        )
    if isinstance(exc, httpx.PoolTimeout):
        return PdfRestPoolTimeoutError(
            str(exc) or "Connection pool timed out while calling pdfRest."
        )
    if isinstance(exc, httpx.TimeoutException):
        return PdfRestTimeoutError(
            str(exc) or "Request timed out while calling pdfRest."
        )
    if isinstance(exc, httpx.TransportError):
        return PdfRestTransportError(
            str(exc) or "Transport-level error while calling pdfRest."
        )
    return PdfRestRequestError(
        str(exc) or "Request failed before receiving a response from pdfRest."
    )
