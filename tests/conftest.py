from __future__ import annotations

import os

import httpx
import pytest

LIVE_BASE_URL_CANDIDATES: tuple[str, ...] = (
    "http://localhost:3000",
    "https://apidev.pdfrest.com",
    "https://api.pdfrest.com",
)


@pytest.fixture(scope="session")
def pdfrest_api_key() -> str:
    key = os.getenv("PDFREST_API_KEY")
    if not key:
        pytest.fail("PDFREST_API_KEY is not configured.")
    return key


@pytest.fixture(scope="session")
def pdfrest_live_base_url(pdfrest_api_key: str) -> str:
    headers = {"Authorization": f"Bearer {pdfrest_api_key}"}
    timeout = httpx.Timeout(2.0)
    for base_url in LIVE_BASE_URL_CANDIDATES:
        try:
            with httpx.Client(base_url=base_url, timeout=timeout) as client:
                response = client.get("/up", headers=headers)
        except httpx.HTTPError:
            continue
        if response.is_success:
            return base_url
    pytest.fail("No reachable pdfRest API instance for live tests.")
