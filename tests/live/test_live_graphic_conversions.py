from __future__ import annotations

from collections.abc import Iterable
from typing import Any, NamedTuple, get_args

import pytest

from pdfrest import PdfRestApiError, PdfRestClient
from pdfrest.models._internal import (
    BasePdfRestGraphicPayload,
    BmpPdfRestPayload,
    GifPdfRestPayload,
    JpegPdfRestPayload,
    PngPdfRestPayload,
    TiffPdfRestPayload,
)

from ..resources import get_test_resource_path


class _GraphicEndpointSpec(NamedTuple):
    method_name: str
    payload_model: type[BasePdfRestGraphicPayload[Any]]


PNG_PAYLOAD_ONLY: dict[str, _GraphicEndpointSpec] = {
    "png": _GraphicEndpointSpec("convert_to_png", PngPdfRestPayload),
}

PAYLOAD_MODELS: dict[str, _GraphicEndpointSpec] = {
    **PNG_PAYLOAD_ONLY,
    "bmp": _GraphicEndpointSpec("convert_to_bmp", BmpPdfRestPayload),
    "gif": _GraphicEndpointSpec("convert_to_gif", GifPdfRestPayload),
    "jpeg": _GraphicEndpointSpec("convert_to_jpeg", JpegPdfRestPayload),
    "tiff": _GraphicEndpointSpec("convert_to_tiff", TiffPdfRestPayload),
}


def _enumerate_color_models(
    payload_model: type[BasePdfRestGraphicPayload[Any]],
) -> Iterable[str]:
    field = payload_model.model_fields["color_model"]
    return get_args(field.annotation) or ()


def _resolution_bounds(
    payload_model: type[BasePdfRestGraphicPayload[Any]],
) -> tuple[int, int]:
    field = payload_model.model_fields["resolution"]
    ge = field.metadata[0].ge if field.metadata else 12
    le = field.metadata[1].le if len(field.metadata) > 1 else 2400
    return int(ge), int(le)


def _valid_color_cases() -> list[Any]:
    cases = []
    for label, spec in PAYLOAD_MODELS.items():
        for color_model in _enumerate_color_models(spec.payload_model):
            cases.append(
                pytest.param(label, spec, color_model, id=f"{label}-{color_model}")
            )
    return cases


def _invalid_color_cases() -> list[Any]:
    cases = []
    candidates = ("lab", "rgba", "cmyk", "xyz", "ultraviolet", "infrared-spectrum")
    for label, spec in PAYLOAD_MODELS.items():
        allowed = set(_enumerate_color_models(spec.payload_model))
        seen: set[str] = set()
        for value in (*candidates, "not-a-color-model"):
            if value in allowed or value in seen:
                continue
            seen.add(value)
            cases.append(pytest.param(label, spec, value, id=f"{label}-{value}"))
    return cases


_SMOOTHING_VALUES: tuple[str, ...] = ("none", "all", "text", "line", "image")


def _valid_smoothing_cases() -> list[Any]:
    cases = []
    for label, spec in PAYLOAD_MODELS.items():
        for smoothing in _SMOOTHING_VALUES:
            cases.append(
                pytest.param(label, spec, smoothing, id=f"{label}-{smoothing}")
            )
    return cases


def _invalid_smoothing_cases() -> list[Any]:
    cases = []
    invalid_inputs: tuple[Any, ...] = (
        "quantum",
        "super-smooth",
        "line, hyperreal",
    )
    for label, spec in PAYLOAD_MODELS.items():
        for candidate in invalid_inputs:
            case_id = (
                f"{label}-{'-'.join(candidate)}"
                if isinstance(candidate, list)
                else f"{label}-{candidate}"
            )
            cases.append(pytest.param(label, spec, candidate, id=case_id))
    return cases


@pytest.mark.parametrize(
    ("_endpoint_label", "spec", "color_model"),
    _valid_color_cases(),
)
def test_live_graphic_valid_color_models(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    _endpoint_label: str,
    spec: _GraphicEndpointSpec,
    color_model: str,
) -> None:
    resource = get_test_resource_path("report.pdf")
    payload_model = spec.payload_model
    resolution = _resolution_bounds(payload_model)[0]
    with PdfRestClient(
        api_key=pdfrest_api_key, base_url=pdfrest_live_base_url
    ) as client:
        uploaded = client.files.create_from_paths([resource])[0]
        client_method = getattr(client, spec.method_name)
        response = client_method(
            uploaded,
            color_model=color_model,
            resolution=resolution,
        )
        assert response.output_files


@pytest.mark.parametrize(
    ("_endpoint_label", "spec", "invalid_color"),
    _invalid_color_cases(),
)
def test_live_graphic_invalid_color_model(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    _endpoint_label: str,
    spec: _GraphicEndpointSpec,
    invalid_color: str,
) -> None:
    payload_model = spec.payload_model

    resource = get_test_resource_path("report.pdf")
    with PdfRestClient(
        api_key=pdfrest_api_key, base_url=pdfrest_live_base_url
    ) as client:
        uploaded = client.files.create_from_paths([resource])[0]
        client_method = getattr(client, spec.method_name)
        resolution = _resolution_bounds(payload_model)[0]
        with pytest.raises(PdfRestApiError):
            client_method(
                uploaded,
                resolution=resolution,
                extra_body={"color_model": invalid_color},
            )


@pytest.mark.parametrize(
    ("_endpoint_label", "spec"),
    PNG_PAYLOAD_ONLY.items(),
    ids=list(PNG_PAYLOAD_ONLY),
)
@pytest.mark.parametrize(
    ("bound", "offset", "should_raise"),
    [
        pytest.param("min", 0, False, id="min"),
        pytest.param("max", 0, False, id="max"),
        pytest.param("min", -1, True, id="below-min"),
        pytest.param("max", 1, True, id="above-max"),
    ],
)
def test_live_graphic_resolution_bounds(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    _endpoint_label: str,
    spec: _GraphicEndpointSpec,
    bound: str,
    offset: int,
    should_raise: bool,
) -> None:
    payload_model = spec.payload_model
    min_res, max_res = _resolution_bounds(payload_model)
    resource = get_test_resource_path("report.pdf")

    with PdfRestClient(
        api_key=pdfrest_api_key, base_url=pdfrest_live_base_url
    ) as client:
        uploaded = client.files.create_from_paths([resource])[0]
        client_method = getattr(client, spec.method_name)
        base_resolution = min_res if bound == "min" else max_res
        call_kwargs: dict[str, Any] = {"resolution": base_resolution}

        if should_raise:
            call_kwargs["extra_body"] = {"resolution": base_resolution + offset}
            with pytest.raises(PdfRestApiError):
                client_method(uploaded, **call_kwargs)
        else:
            response = client_method(uploaded, **call_kwargs)
            assert response.output_files


@pytest.mark.parametrize(
    ("_endpoint_label", "spec", "smoothing_value"),
    _valid_smoothing_cases(),
)
def test_live_graphic_valid_smoothing(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    _endpoint_label: str,
    spec: _GraphicEndpointSpec,
    smoothing_value: str,
) -> None:
    resource = get_test_resource_path("report.pdf")
    with PdfRestClient(
        api_key=pdfrest_api_key, base_url=pdfrest_live_base_url
    ) as client:
        uploaded = client.files.create_from_paths([resource])[0]
        client_method = getattr(client, spec.method_name)
        response = client_method(
            uploaded,
            smoothing=smoothing_value,
        )
        assert response.output_files


@pytest.mark.parametrize(
    ("_endpoint_label", "spec", "invalid_smoothing"),
    _invalid_smoothing_cases(),
)
def test_live_graphic_invalid_smoothing(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    _endpoint_label: str,
    spec: _GraphicEndpointSpec,
    invalid_smoothing: Any,
) -> None:
    resource = get_test_resource_path("report.pdf")
    with PdfRestClient(
        api_key=pdfrest_api_key, base_url=pdfrest_live_base_url
    ) as client:
        uploaded = client.files.create_from_paths([resource])[0]
        client_method = getattr(client, spec.method_name)
        with pytest.raises(PdfRestApiError):
            client_method(
                uploaded,
                smoothing="none",
                extra_body={"smoothing": invalid_smoothing},
            )
