from __future__ import annotations

import os
from typing import Any

import pytest

from pdfrest import AsyncPdfRestClient, PdfRestClient

DEFAULT_LIVE_WSN = "dl-internal-python-ci"


def _with_live_wsn_header(kwargs: dict[str, Any], wsn: str) -> dict[str, Any]:
    new_kwargs = dict(kwargs)
    headers = dict(new_kwargs.get("headers") or {})
    headers["wsn"] = wsn
    new_kwargs["headers"] = headers
    return new_kwargs


@pytest.fixture(scope="session")
def pdfrest_live_wsn() -> str:
    return os.getenv("PDFREST_LIVE_WSN", DEFAULT_LIVE_WSN)


@pytest.fixture(autouse=True)
def inject_live_test_wsn_header(
    monkeypatch: pytest.MonkeyPatch,
    pdfrest_live_wsn: str,
) -> None:
    original_sync_init = PdfRestClient.__init__
    original_async_init = AsyncPdfRestClient.__init__

    def sync_init_with_live_header(
        self: PdfRestClient,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        original_sync_init(
            self,
            *args,
            **_with_live_wsn_header(kwargs, pdfrest_live_wsn),
        )

    def async_init_with_live_header(
        self: AsyncPdfRestClient,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        original_async_init(
            self,
            *args,
            **_with_live_wsn_header(kwargs, pdfrest_live_wsn),
        )

    monkeypatch.setattr(PdfRestClient, "__init__", sync_init_with_live_header)
    monkeypatch.setattr(AsyncPdfRestClient, "__init__", async_init_with_live_header)
    return
