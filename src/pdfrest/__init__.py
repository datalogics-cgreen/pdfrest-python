"""Top-level package for the pdfrest client library."""

from importlib import metadata

__all__ = ("__version__",)

try:  # pragma: no cover - fallback should never run in production builds
    __version__ = metadata.version("pdfrest")
except metadata.PackageNotFoundError:  # pragma: no cover
    __version__ = "0.0.0"
