from __future__ import annotations

from uuid import uuid4

import pytest

from pdfrest import AsyncPdfRestClient, PdfRestApiError, PdfRestClient
from pdfrest.models import PdfRestFile

from ..resources import get_test_resource_path


def make_password(label: str) -> str:
    return f"{label}-{uuid4().hex}"


@pytest.fixture(scope="module")
def uploaded_pdf_for_encrypt(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
) -> PdfRestFile:
    resource = get_test_resource_path("report.pdf")
    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        return client.files.create_from_paths([resource])[0]


def test_live_add_open_password(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf_for_encrypt: PdfRestFile,
) -> None:
    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        response = client.add_open_password(
            uploaded_pdf_for_encrypt,
            new_open_password=make_password("live-open"),
            output="live-encrypted",
        )

    assert response.output_files
    output_file = response.output_file
    assert output_file.type == "application/pdf"
    assert output_file.name.startswith("live-encrypted")
    assert str(response.input_id) == str(uploaded_pdf_for_encrypt.id)


@pytest.mark.asyncio
async def test_live_async_add_open_password(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf_for_encrypt: PdfRestFile,
) -> None:
    async with AsyncPdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        response = await client.add_open_password(
            uploaded_pdf_for_encrypt,
            new_open_password=make_password("async-live-open"),
            output="async-live-encrypted",
        )

    assert response.output_files
    output_file = response.output_file
    assert output_file.type == "application/pdf"
    assert output_file.name.startswith("async-live-encrypted")
    assert str(response.input_id) == str(uploaded_pdf_for_encrypt.id)


def test_live_change_open_password(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf_for_encrypt: PdfRestFile,
) -> None:
    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        current_password = make_password("live-open-current")
        restricted = client.add_open_password(
            uploaded_pdf_for_encrypt,
            new_open_password=current_password,
            output="live-open-old",
        ).output_file
        response = client.change_open_password(
            restricted,
            current_open_password=current_password,
            new_open_password=make_password("live-open-new"),
            output="live-open-new",
        )

    assert response.output_files
    output_file = response.output_file
    assert output_file.name.startswith("live-open-new")
    assert output_file.type == "application/pdf"
    assert str(response.input_id) == str(restricted.id)


@pytest.mark.asyncio
async def test_live_async_change_open_password(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf_for_encrypt: PdfRestFile,
) -> None:
    async with AsyncPdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        current_password = make_password("async-live-open-current")
        restricted = (
            await client.add_open_password(
                uploaded_pdf_for_encrypt,
                new_open_password=current_password,
                output="async-live-open-old",
            )
        ).output_file
        response = await client.change_open_password(
            restricted,
            current_open_password=current_password,
            new_open_password=make_password("async-live-open-new"),
            output="async-live-open-new",
        )

    assert response.output_files
    output_file = response.output_file
    assert output_file.name.startswith("async-live-open-new")
    assert output_file.type == "application/pdf"
    assert str(response.input_id) == str(restricted.id)


def test_live_remove_open_password(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf_for_encrypt: PdfRestFile,
) -> None:
    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        current_password = make_password("live-open-remove")
        restricted = client.add_open_password(
            uploaded_pdf_for_encrypt,
            new_open_password=current_password,
            output="live-open-to-remove",
        ).output_file
        response = client.remove_open_password(
            restricted,
            current_open_password=current_password,
            output="live-open-removed",
        )

    assert response.output_files
    output_file = response.output_file
    assert output_file.type == "application/pdf"
    assert output_file.name.startswith("live-open-removed")
    assert str(response.input_id) == str(restricted.id)


@pytest.mark.asyncio
async def test_live_async_remove_open_password(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf_for_encrypt: PdfRestFile,
) -> None:
    async with AsyncPdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        current_password = make_password("async-live-open-remove")
        restricted = (
            await client.add_open_password(
                uploaded_pdf_for_encrypt,
                new_open_password=current_password,
                output="async-live-open-to-remove",
            )
        ).output_file
        response = await client.remove_open_password(
            restricted,
            current_open_password=current_password,
            output="async-live-open-removed",
        )

    assert response.output_files
    output_file = response.output_file
    assert output_file.type == "application/pdf"
    assert output_file.name.startswith("async-live-open-removed")
    assert str(response.input_id) == str(restricted.id)


def test_live_remove_open_password_invalid_password(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf_for_encrypt: PdfRestFile,
) -> None:
    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        correct_password = make_password("live-open-correct")
        wrong_password = make_password("live-open-wrong")
        restricted = client.add_open_password(
            uploaded_pdf_for_encrypt,
            new_open_password=correct_password,
            output="live-open-invalid",
        ).output_file
        with pytest.raises(PdfRestApiError, match="password-protected"):
            client.remove_open_password(
                restricted,
                current_open_password=wrong_password,
            )


@pytest.mark.asyncio
async def test_live_async_remove_open_password_invalid_password(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf_for_encrypt: PdfRestFile,
) -> None:
    async with AsyncPdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        correct_password = make_password("async-live-open-correct")
        wrong_password = make_password("async-live-open-wrong")
        restricted = (
            await client.add_open_password(
                uploaded_pdf_for_encrypt,
                new_open_password=correct_password,
                output="async-live-open-invalid",
            )
        ).output_file
        with pytest.raises(PdfRestApiError, match="password-protected"):
            await client.remove_open_password(
                restricted,
                current_open_password=wrong_password,
            )
