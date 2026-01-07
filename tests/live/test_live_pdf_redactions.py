from __future__ import annotations

from typing import get_args

import pytest

from pdfrest import AsyncPdfRestClient, PdfRestApiError, PdfRestClient
from pdfrest.models import PdfRestFile
from pdfrest.types import PdfRedactionInstruction, PdfRedactionPreset

from ..resources import get_test_resource_path


@pytest.fixture(scope="module")
def uploaded_pdf_for_redaction(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
) -> PdfRestFile:
    resource = get_test_resource_path("redactable-text.pdf")
    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        return client.files.create_from_paths([resource])[0]


@pytest.mark.parametrize(
    "instruction",
    [
        pytest.param(
            {
                "type": "literal",
                "value": "The quick brown fox jumped over the lazy dog.",
            },
            id="literal",
        ),
        pytest.param({"type": "regex", "value": r"\b\d{3}-\d{2}-\d{4}\b"}, id="regex"),
        *[
            pytest.param({"type": "preset", "value": preset}, id=f"preset-{preset}")
            for preset in get_args(PdfRedactionPreset)
        ],
    ],
)
def test_live_redaction_preview_and_apply_single(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf_for_redaction: PdfRestFile,
    instruction: PdfRedactionInstruction,
) -> None:
    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        preview = client.preview_redactions(
            uploaded_pdf_for_redaction,
            redactions=[instruction],
            output="redaction-preview",
        )

        assert preview.output_files
        preview_file = preview.output_files[0]
        assert preview_file.name.endswith("redaction-preview.pdf")
        assert preview_file.type == "application/pdf"

        applied = client.apply_redactions(
            preview_file,
            output="redaction-final",
        )

        assert applied.output_files
        final_file = applied.output_files[0]
        assert final_file.name.endswith("redaction-final.pdf")
        assert final_file.type == "application/pdf"


@pytest.mark.parametrize(
    "instructions",
    [
        pytest.param(
            [
                {
                    "type": "literal",
                    "value": "The quick brown fox jumped over the lazy dog.",
                },
                {"type": "regex", "value": r"\b\d{3}-\d{2}-\d{4}\b"},
            ],
            id="literal-and-regex",
        ),
        pytest.param(
            [
                {"type": "preset", "value": "email"},
                {"type": "preset", "value": "phone_number"},
            ],
            id="preset-email-and-phone",
        ),
        pytest.param(
            [
                {"type": "preset", "value": "credit_card"},
                {"type": "preset", "value": "bank_routing_number"},
                {"type": "preset", "value": "swift_bic_number"},
            ],
            id="multiple-presets",
        ),
    ],
)
def test_live_redaction_preview_and_apply_multiple(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf_for_redaction: PdfRestFile,
    instructions: list[PdfRedactionInstruction],
) -> None:
    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        preview = client.preview_redactions(
            uploaded_pdf_for_redaction,
            redactions=instructions,
            output="redaction-preview-multi",
        )

        assert preview.output_files
        preview_file = preview.output_files[0]
        assert preview_file.name.endswith("redaction-preview-multi.pdf")
        assert preview_file.type == "application/pdf"

        applied = client.apply_redactions(
            preview_file,
            output="redaction-final-multi",
        )

        assert applied.output_files
        final_file = applied.output_files[0]
        assert final_file.name.endswith("redaction-final-multi.pdf")
        assert final_file.type == "application/pdf"


@pytest.mark.asyncio
async def test_live_async_redaction_preview_and_apply(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf_for_redaction: PdfRestFile,
) -> None:
    async with AsyncPdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        preview = await client.preview_redactions(
            uploaded_pdf_for_redaction,
            redactions=[{"type": "literal", "value": "quick brown fox"}],
            output="async-redaction-preview",
        )

        preview_file = preview.output_files[0]
        applied = await client.apply_redactions(
            preview_file,
            output="async-redaction-final",
        )

    assert preview.output_files
    assert preview_file.name.endswith("async-redaction-preview.pdf")
    assert applied.output_files
    final_file = applied.output_files[0]
    assert final_file.name.endswith("async-redaction-final.pdf")
    assert final_file.type == "application/pdf"


@pytest.mark.parametrize(
    "extra_body",
    [
        pytest.param({"redactions": "invalid"}, id="invalid-redactions"),
        pytest.param({"rgb_color": "-1,-1,-1"}, id="invalid-rgb"),
    ],
)
def test_live_redactions_invalid_payloads(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf_for_redaction: PdfRestFile,
    extra_body: dict[str, object],
) -> None:
    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        if "redactions" in extra_body:
            with pytest.raises(
                PdfRestApiError,
                match=(
                    r"The JSON data provided is not properly formatted\. Please check "
                    r"your syntax and try again\."
                ),
            ):
                client.preview_redactions(
                    uploaded_pdf_for_redaction,
                    redactions=[{"type": "literal", "value": "placeholder"}],
                    extra_body=extra_body,
                )
        else:
            preview = client.preview_redactions(
                uploaded_pdf_for_redaction,
                redactions=[{"type": "literal", "value": "placeholder"}],
            )
            preview_file = preview.output_files[0]
            with pytest.raises(PdfRestApiError, match=r"(?i)rgb"):
                client.apply_redactions(preview_file, extra_body=extra_body)


@pytest.mark.asyncio
async def test_live_async_redactions_invalid_payloads(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf_for_redaction: PdfRestFile,
) -> None:
    async with AsyncPdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        with pytest.raises(PdfRestApiError, match=r"(?i)rgb"):
            await client.preview_redactions(
                uploaded_pdf_for_redaction,
                redactions=[{"type": "literal", "value": "placeholder"}],
                extra_body={"rgb_color": "-1,-1,-1"},
            )
