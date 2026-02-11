from __future__ import annotations

from typing import cast, get_args

import pytest

from pdfrest import AsyncPdfRestClient, PdfRestApiError, PdfRestClient
from pdfrest.models import PdfRestFile
from pdfrest.types import PdfColorProfile

from ..resources import get_test_resource_path

ALL_COLOR_PROFILES: tuple[PdfColorProfile, ...] = cast(
    tuple[PdfColorProfile, ...],
    get_args(PdfColorProfile),
)
PRESET_COLOR_PROFILES: tuple[PdfColorProfile, ...] = tuple(
    color_profile for color_profile in ALL_COLOR_PROFILES if color_profile != "custom"
)


@pytest.fixture(scope="module")
def uploaded_pdf_for_color_conversion(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
) -> PdfRestFile:
    resource = get_test_resource_path("report.pdf")
    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        return client.files.create_from_paths([resource])[0]


@pytest.mark.parametrize(
    "color_profile",
    [
        pytest.param(color_profile, id=f"color-profile-{color_profile}")
        for color_profile in PRESET_COLOR_PROFILES
    ],
)
def test_live_convert_colors_presets_success(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf_for_color_conversion: PdfRestFile,
    color_profile: PdfColorProfile,
) -> None:
    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        response = client.convert_colors(
            uploaded_pdf_for_color_conversion,
            color_profile=color_profile,
        )

    assert response.output_files
    output_file = response.output_file
    assert output_file.type == "application/pdf"
    assert output_file.size > 0
    assert response.warning is None
    assert str(response.input_id) == str(uploaded_pdf_for_color_conversion.id)


@pytest.mark.parametrize(
    "output_name",
    [
        pytest.param(None, id="default-output"),
        pytest.param("converted-colors", id="custom-output"),
    ],
)
def test_live_convert_colors_output_prefix(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf_for_color_conversion: PdfRestFile,
    output_name: str | None,
) -> None:
    kwargs: dict[str, str] = {"color_profile": "srgb"}
    if output_name is not None:
        kwargs["output"] = output_name

    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        response = client.convert_colors(uploaded_pdf_for_color_conversion, **kwargs)

    assert response.output_files
    output_file = response.output_file
    assert output_file.type == "application/pdf"
    assert output_file.size > 0
    assert response.warning is None
    assert str(response.input_id) == str(uploaded_pdf_for_color_conversion.id)
    if output_name is not None:
        assert output_file.name.startswith(output_name)
    else:
        assert output_file.name.endswith(".pdf")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "color_profile",
    [
        pytest.param(color_profile, id=f"color-profile-{color_profile}")
        for color_profile in PRESET_COLOR_PROFILES
    ],
)
async def test_live_async_convert_colors_presets_success(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf_for_color_conversion: PdfRestFile,
    color_profile: PdfColorProfile,
) -> None:
    async with AsyncPdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        response = await client.convert_colors(
            uploaded_pdf_for_color_conversion,
            color_profile=color_profile,
        )

    assert response.output_files
    output_file = response.output_file
    assert output_file.type == "application/pdf"
    assert output_file.size > 0
    assert response.warning is None
    assert str(response.input_id) == str(uploaded_pdf_for_color_conversion.id)


@pytest.mark.asyncio
async def test_live_async_convert_colors_output_prefix(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf_for_color_conversion: PdfRestFile,
) -> None:
    async with AsyncPdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        response = await client.convert_colors(
            uploaded_pdf_for_color_conversion,
            color_profile="srgb",
            output="async",
        )

    assert response.output_files
    output_file = response.output_file
    assert output_file.name.startswith("async")
    assert output_file.type == "application/pdf"
    assert output_file.size > 0
    assert response.warning is None
    assert str(response.input_id) == str(uploaded_pdf_for_color_conversion.id)


def test_live_convert_colors_invalid_color_profile(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf_for_color_conversion: PdfRestFile,
) -> None:
    with (
        PdfRestClient(
            api_key=pdfrest_api_key,
            base_url=pdfrest_live_base_url,
        ) as client,
        pytest.raises(PdfRestApiError, match=r"(?i)(color|profile)"),
    ):
        client.convert_colors(
            uploaded_pdf_for_color_conversion,
            color_profile="srgb",
            extra_body={"color_profile": "not-a-color-profile"},
        )


@pytest.mark.asyncio
async def test_live_async_convert_colors_invalid_color_profile(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf_for_color_conversion: PdfRestFile,
) -> None:
    async with AsyncPdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        with pytest.raises(PdfRestApiError, match=r"(?i)(color|profile)"):
            await client.convert_colors(
                uploaded_pdf_for_color_conversion,
                color_profile="srgb",
                extra_body={"color_profile": "not-a-color-profile"},
            )


def test_live_convert_colors_invalid_file_id(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf_for_color_conversion: PdfRestFile,
) -> None:
    with (
        PdfRestClient(
            api_key=pdfrest_api_key,
            base_url=pdfrest_live_base_url,
        ) as client,
        pytest.raises(PdfRestApiError, match=r"(?i)(id|file)"),
    ):
        client.convert_colors(
            uploaded_pdf_for_color_conversion,
            color_profile="srgb",
            extra_body={"id": "00000000-0000-0000-0000-000000000000"},
        )


@pytest.mark.asyncio
async def test_live_async_convert_colors_invalid_file_id(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf_for_color_conversion: PdfRestFile,
) -> None:
    async with AsyncPdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        with pytest.raises(PdfRestApiError, match=r"(?i)(id|file)"):
            await client.convert_colors(
                uploaded_pdf_for_color_conversion,
                color_profile="srgb",
                extra_body={"id": "ffffffff-ffff-ffff-ffff-ffffffffffff"},
            )
