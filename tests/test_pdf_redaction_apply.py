from __future__ import annotations

import json

import httpx
import pytest
from pydantic import ValidationError

from pdfrest import PdfRestClient
from pdfrest.models import PdfRestFileBasedResponse, PdfRestFileID
from pdfrest.models._internal import PdfRedactionApplyPayload
from pdfrest.types import PdfRGBColor

from .graphics_test_helpers import VALID_API_KEY, build_file_info_payload, make_pdf_file


@pytest.mark.parametrize(
    "rgb_color",
    [
        pytest.param((255, 255, 255), id="tuple"),
        pytest.param([10, 20, 30], id="list"),
        pytest.param(None, id="none"),
    ],
)
def test_apply_redactions_success(
    monkeypatch: pytest.MonkeyPatch,
    rgb_color: PdfRGBColor | list[int] | None,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(1))
    output_id = str(PdfRestFileID.generate())

    payload_data: dict[str, object] = {"files": [input_file]}
    if rgb_color is not None:
        payload_data["rgb_color"] = rgb_color
    payload_data["output"] = "final-output"

    payload_model_dump = PdfRedactionApplyPayload.model_validate(
        payload_data
    ).model_dump(mode="json", by_alias=True, exclude_none=True, exclude_unset=True)

    def handler(request: httpx.Request) -> httpx.Response:
        if (
            request.method == "POST"
            and request.url.path == "/pdf-with-redacted-text-applied"
        ):
            body = json.loads(request.content.decode("utf-8"))
            assert body == payload_model_dump
            return httpx.Response(
                200,
                json={
                    "inputId": [input_file.id],
                    "outputId": [output_id],
                },
            )
        if request.method == "GET" and request.url.path == f"/resource/{output_id}":
            return httpx.Response(
                200,
                json=build_file_info_payload(
                    output_id, "final-output.pdf", "application/pdf"
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.apply_redactions(
            input_file,
            rgb_color=rgb_color,
            output="final-output",
        )

    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.output_files[0].name == "final-output.pdf"
    assert response.output_files[0].type == "application/pdf"


def test_apply_redactions_invalid_color(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_pdf_file(PdfRestFileID.generate(1))
    transport = httpx.MockTransport(lambda request: (_ for _ in ()).throw(RuntimeError))

    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        with pytest.raises(ValidationError, match="Field required"):
            client.apply_redactions(input_file, rgb_color=[255, 255])

        with pytest.raises(ValidationError, match="greater than or equal to 0"):
            client.apply_redactions(input_file, rgb_color=[-1, 0, 0])
