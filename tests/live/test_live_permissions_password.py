from __future__ import annotations

from typing import cast, get_args
from uuid import uuid4

import pytest

from pdfrest import AsyncPdfRestClient, PdfRestApiError, PdfRestClient
from pdfrest.models import PdfRestFile, PdfRestFileBasedResponse
from pdfrest.types import PdfRestriction

from ..resources import get_test_resource_path


def make_password(label: str) -> str:
    return f"{label}-{uuid4().hex}"


def assert_pdf_file_response(
    response: PdfRestFileBasedResponse,
    *,
    output_prefix: str,
    input_file: PdfRestFile,
) -> None:
    assert response.output_files
    output_file = response.output_file
    assert output_file.type == "application/pdf"
    assert output_file.name.startswith(output_prefix)
    assert output_file.name.endswith(".pdf")
    assert output_file.size > 0
    assert response.warning is None
    assert str(response.input_id) == str(input_file.id)


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

    assert_pdf_file_response(
        response,
        output_prefix="live-restrict",
        input_file=uploaded_pdf_for_permissions,
    )


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

    assert_pdf_file_response(
        response,
        output_prefix="async-restrict",
        input_file=uploaded_pdf_for_permissions,
    )


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

    assert_pdf_file_response(
        response,
        output_prefix="live-restrict-new",
        input_file=restricted_file,
    )


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

    assert_pdf_file_response(
        response,
        output_prefix="async-live-restrict-new",
        input_file=restricted_file,
    )


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

    assert_pdf_file_response(
        response,
        output_prefix="live-removed",
        input_file=restricted_file,
    )


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

    assert_pdf_file_response(
        response,
        output_prefix="async-live-removed",
        input_file=restricted_file,
    )


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


def test_live_add_permissions_password_invalid_restriction(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf_for_permissions: PdfRestFile,
) -> None:
    invalid_restriction = "totally-invalid-restriction"
    with (
        PdfRestClient(
            api_key=pdfrest_api_key,
            base_url=pdfrest_live_base_url,
        ) as client,
        pytest.raises(PdfRestApiError, match=r"(?i)restriction|invalid"),
    ):
        client.add_permissions_password(
            uploaded_pdf_for_permissions,
            new_permissions_password=make_password("live-invalid-restriction"),
            restrictions=["print_low"],
            extra_body={"restrictions": [invalid_restriction]},
        )


@pytest.mark.asyncio
async def test_live_async_add_permissions_password_invalid_restriction(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf_for_permissions: PdfRestFile,
) -> None:
    invalid_restriction = "totally-invalid-restriction"
    async with AsyncPdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        with pytest.raises(PdfRestApiError, match=r"(?i)restriction|invalid"):
            await client.add_permissions_password(
                uploaded_pdf_for_permissions,
                new_permissions_password=make_password(
                    "async-live-invalid-restriction"
                ),
                restrictions=["print_low"],
                extra_body={"restrictions": [invalid_restriction]},
            )
