from __future__ import annotations

from secrets import token_urlsafe

import pytest
from pydantic import ValidationError

from pdfrest import (
    AsyncPdfRestClient,
    PdfRestClient,
    PdfRestDeleteError,
    PdfRestErrorGroup,
)
from pdfrest.models import PdfRestFileID

from ..resources import get_test_resource_path


def test_live_delete_files_success(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
) -> None:
    resource = get_test_resource_path("report.pdf")
    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        uploaded = client.files.create_from_paths([resource])[0]
        result = client.files.delete(uploaded)

    assert result is None


@pytest.mark.asyncio
async def test_live_async_delete_files_success(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
) -> None:
    resource = get_test_resource_path("report.pdf")
    async with AsyncPdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        uploaded = (await client.files.create_from_paths([resource]))[0]
        result = await client.files.delete(uploaded)

    assert result is None


def test_live_delete_files_invalid_id(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
) -> None:
    resource = get_test_resource_path("report.pdf")
    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        uploaded = client.files.create_from_paths([resource])[0]
        with pytest.raises(ValidationError):
            client.files.delete(uploaded, extra_body={"ids": token_urlsafe(16)})


@pytest.mark.asyncio
async def test_live_async_delete_files_invalid_id(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
) -> None:
    resource = get_test_resource_path("report.pdf")
    async with AsyncPdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        uploaded = (await client.files.create_from_paths([resource]))[0]
        with pytest.raises(ValidationError):
            await client.files.delete(uploaded, extra_body={"ids": token_urlsafe(16)})


def test_live_delete_files_missing_id(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
) -> None:
    resource = get_test_resource_path("report.pdf")
    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        bad_id_1 = PdfRestFileID.generate()
        bad_id_2 = PdfRestFileID.generate()
        uploaded = client.files.create_from_paths([resource])[0]
        with pytest.RaisesGroup(
            pytest.RaisesExc(
                PdfRestDeleteError,
                match=f"Failed to delete file {bad_id_1}.*does not exist",
            ),
            pytest.RaisesExc(
                PdfRestDeleteError,
                match=f"Failed to delete file {bad_id_2}.*does not exist",
            ),
            match="Failed to delete one or more files.",
            check=lambda eg: isinstance(eg, PdfRestErrorGroup),
        ):
            client.files.delete(
                uploaded, extra_body={"ids": ",".join([bad_id_1, bad_id_2])}
            )


@pytest.mark.asyncio
async def test_live_async_delete_files_missing_id(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
) -> None:
    resource = get_test_resource_path("report.pdf")
    async with AsyncPdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        bad_id_1 = PdfRestFileID.generate()
        bad_id_2 = PdfRestFileID.generate()
        uploaded = (await client.files.create_from_paths([resource]))[0]
        with pytest.RaisesGroup(
            pytest.RaisesExc(
                PdfRestDeleteError,
                match=f"Failed to delete file {bad_id_1}.*does not exist",
            ),
            pytest.RaisesExc(
                PdfRestDeleteError,
                match=f"Failed to delete file {bad_id_2}.*does not exist",
            ),
            match="Failed to delete one or more files.",
            check=lambda eg: isinstance(eg, PdfRestErrorGroup),
        ):
            await client.files.delete(
                uploaded, extra_body={"ids": ",".join([bad_id_1, bad_id_2])}
            )
