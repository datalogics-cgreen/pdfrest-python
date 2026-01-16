from __future__ import annotations

from typing import cast, get_args
from uuid import uuid4

import pytest

from pdfrest import AsyncPdfRestClient, PdfRestApiError, PdfRestClient
from pdfrest.models import PdfRestFile
from pdfrest.types import PdfRestriction

from ..resources import get_test_resource_path


def make_password(label: str) -> str:
    return f"{label}-{uuid4().hex}"


PDF_RESTRICTIONS: tuple[PdfRestriction, ...] = cast(
    tuple[PdfRestriction, ...], get_args(PdfRestriction)
)
RESTRICTION_PARAMS = [
    pytest.param(restriction, id=restriction) for restriction in PDF_RESTRICTIONS
]


@pytest.fixture(scope="module")
def uploaded_pdf_for_permissions(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
) -> PdfRestFile:
    resource = get_test_resource_path("report.pdf")
    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        return client.files.create_from_paths([resource])[0]


@pytest.mark.parametrize("restriction", RESTRICTION_PARAMS)
def test_live_add_permissions_password(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf_for_permissions: PdfRestFile,
    restriction: PdfRestriction,
) -> None:
    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        new_password = make_password("live-perm")
        response = client.add_permissions_password(
            uploaded_pdf_for_permissions,
            new_permissions_password=new_password,
            restrictions=[restriction],
            output="live-restrict",
        )

    assert response.output_files
    output_file = response.output_file
    assert output_file.type == "application/pdf"
    assert output_file.name.startswith("live-restrict")
    assert str(response.input_id) == str(uploaded_pdf_for_permissions.id)


@pytest.mark.asyncio
@pytest.mark.parametrize("restriction", RESTRICTION_PARAMS)
async def test_live_async_add_permissions_password(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf_for_permissions: PdfRestFile,
    restriction: PdfRestriction,
) -> None:
    async with AsyncPdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        new_password = make_password("async-live-perm")
        response = await client.add_permissions_password(
            uploaded_pdf_for_permissions,
            new_permissions_password=new_password,
            restrictions=[restriction],
            output="async-restrict",
        )

    assert response.output_files
    output_file = response.output_file
    assert output_file.type == "application/pdf"
    assert output_file.name.startswith("async-restrict")
    assert str(response.input_id) == str(uploaded_pdf_for_permissions.id)


def test_live_change_permissions_password(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf_for_permissions: PdfRestFile,
) -> None:
    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        current_password = make_password("old-live")
        new_password = make_password("new-live")
        restricted_response = client.add_permissions_password(
            uploaded_pdf_for_permissions,
            new_permissions_password=current_password,
            restrictions=["print_low"],
            output="live-restrict-old",
        )
        restricted_file = restricted_response.output_file
        response = client.change_permissions_password(
            restricted_file,
            current_permissions_password=current_password,
            new_permissions_password=new_password,
            restrictions=["copy_content"],
            output="live-restrict-new",
        )

    assert response.output_files
    output_file = response.output_file
    assert output_file.name.startswith("live-restrict-new")
    assert output_file.type == "application/pdf"
    assert str(response.input_id) == str(restricted_file.id)


@pytest.mark.asyncio
async def test_live_async_change_permissions_password(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf_for_permissions: PdfRestFile,
) -> None:
    async with AsyncPdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        current_password = make_password("async-old")
        new_password = make_password("async-new")
        restricted_response = await client.add_permissions_password(
            uploaded_pdf_for_permissions,
            new_permissions_password=current_password,
            restrictions=["edit_content"],
            output="async-live-restrict-old",
        )
        restricted_file = restricted_response.output_file
        response = await client.change_permissions_password(
            restricted_file,
            current_permissions_password=current_password,
            new_permissions_password=new_password,
            restrictions=["edit_annotations"],
            output="async-live-restrict-new",
        )

    assert response.output_files
    output_file = response.output_file
    assert output_file.name.startswith("async-live-restrict-new")
    assert output_file.type == "application/pdf"
    assert str(response.input_id) == str(restricted_file.id)


def test_live_remove_permissions_password(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf_for_permissions: PdfRestFile,
) -> None:
    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        current_password = make_password("remove-live")
        restricted_response = client.add_permissions_password(
            uploaded_pdf_for_permissions,
            new_permissions_password=current_password,
            restrictions=["print_high"],
            output="live-to-remove",
        )
        restricted_file = restricted_response.output_file
        response = client.remove_permissions_password(
            restricted_file,
            current_permissions_password=current_password,
            output="live-removed",
        )

    assert response.output_files
    output_file = response.output_file
    assert output_file.name.startswith("live-removed")
    assert output_file.type == "application/pdf"
    assert str(response.input_id) == str(restricted_file.id)


@pytest.mark.asyncio
async def test_live_async_remove_permissions_password(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf_for_permissions: PdfRestFile,
) -> None:
    async with AsyncPdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        current_password = make_password("async-remove")
        restricted_response = await client.add_permissions_password(
            uploaded_pdf_for_permissions,
            new_permissions_password=current_password,
            restrictions=["accessibility_off"],
            output="async-live-to-remove",
        )
        restricted_file = restricted_response.output_file
        response = await client.remove_permissions_password(
            restricted_file,
            current_permissions_password=current_password,
            output="async-live-removed",
        )

    assert response.output_files
    output_file = response.output_file
    assert output_file.name.startswith("async-live-removed")
    assert output_file.type == "application/pdf"
    assert str(response.input_id) == str(restricted_file.id)


def test_live_remove_permissions_password_invalid_password(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf_for_permissions: PdfRestFile,
) -> None:
    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        correct_password = make_password("live-wrong")
        wrong_password = make_password("incorrect")
        restricted_response = client.add_permissions_password(
            uploaded_pdf_for_permissions,
            new_permissions_password=correct_password,
            restrictions=["edit_annotations"],
            output="live-invalid-remove",
        )
        restricted_file = restricted_response.output_file
        with pytest.raises(PdfRestApiError, match="permissions password"):
            client.remove_permissions_password(
                restricted_file,
                current_permissions_password=wrong_password,
            )


@pytest.mark.asyncio
async def test_live_async_remove_permissions_password_invalid_password(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf_for_permissions: PdfRestFile,
) -> None:
    async with AsyncPdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        correct_password = make_password("async-live-wrong")
        wrong_password = make_password("async-wrong")
        restricted_response = await client.add_permissions_password(
            uploaded_pdf_for_permissions,
            new_permissions_password=correct_password,
            restrictions=["edit_content"],
            output="async-live-invalid-remove",
        )
        restricted_file = restricted_response.output_file
        with pytest.raises(PdfRestApiError, match="permissions password"):
            await client.remove_permissions_password(
                restricted_file,
                current_permissions_password=wrong_password,
            )
