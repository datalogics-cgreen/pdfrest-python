"""Sync and async client interfaces for the pdfrest API."""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any, Generic, Literal, TypedDict, TypeVar, cast

import httpx
from httpx import URL
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from .exceptions import (
    PdfRestApiError,
    PdfRestConfigurationError,
    translate_httpx_error,
)
from .models import PdfRestErrorResponse, UpResponse

__all__ = ("AsyncPdfRestClient", "PdfRestClient", "RequestOptions", "UpRequestOptions")

DEFAULT_BASE_URL = "https://api.pdfrest.com"
API_KEY_ENV_VAR = "PDFREST_API_KEY"
DEFAULT_TIMEOUT_SECONDS = 10.0

HttpMethod = Literal["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"]
QueryParamValue = str | int | float | bool | None
TimeoutTypes = float | httpx.Timeout | None


ClientType = TypeVar("ClientType", httpx.Client, httpx.AsyncClient)


class RequestOptions(TypedDict, total=False):
    """Shared request customisation options for pdfrest endpoints."""

    headers: Mapping[str, str]
    params: Mapping[str, QueryParamValue]
    timeout: float | httpx.Timeout


UpRequestOptions = RequestOptions


class _ClientConfig(BaseModel):
    """Internal representation of client configuration validated by Pydantic."""

    base_url: URL
    api_key: str
    timeout: TimeoutTypes = DEFAULT_TIMEOUT_SECONDS
    headers: dict[str, str] = Field(default_factory=dict)

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @field_validator("base_url", mode="before")
    @classmethod
    def _parse_base_url(cls, value: Any) -> URL:
        url_value = value or DEFAULT_BASE_URL
        url = URL(str(url_value))
        if url.scheme not in {"http", "https"}:
            msg = "base_url must use http or https scheme."
            raise PdfRestConfigurationError(msg)
        return (
            url
            if not url.path or url.path == "/"
            else url.copy_with(path=url.path.rstrip("/"))
        )

    @field_validator("api_key")
    @classmethod
    def _validate_api_key(cls, value: str) -> str:
        if not value or not value.strip():
            msg = "API key must not be empty."
            raise PdfRestConfigurationError(msg)
        return value.strip()

    @field_validator("headers", mode="before")
    @classmethod
    def _validate_headers(cls, value: Any) -> dict[str, str]:
        if value is None:
            return {}
        converted: dict[str, str] = {}
        for key, item in dict(value).items():
            converted[str(key)] = str(item)
        return converted

    @field_validator("timeout", mode="before")
    @classmethod
    def _validate_timeout(cls, value: Any) -> TimeoutTypes:
        if value is None:
            return DEFAULT_TIMEOUT_SECONDS
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, httpx.Timeout):
            return value
        msg = "timeout must be a float (seconds) or httpx.Timeout instance."
        raise PdfRestConfigurationError(msg)


class _RequestModel(BaseModel):
    """Internal request data validated prior to dispatch."""

    method: HttpMethod
    endpoint: str
    params: dict[str, str] | None = None
    headers: dict[str, str] = Field(default_factory=dict)
    timeout: TimeoutTypes

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @field_validator("endpoint")
    @classmethod
    def _validate_endpoint(cls, value: str) -> str:
        if not value.startswith("/"):
            msg = "endpoint must start with '/'."
            raise PdfRestConfigurationError(msg)
        return value

    @field_validator("params", mode="before")
    @classmethod
    def _normalize_params(cls, value: Any) -> dict[str, str]:
        if value is None:
            return {}
        normalized: dict[str, str] = {}
        for key, candidate in dict(value).items():
            if candidate is None:
                continue
            normalized[str(key)] = str(candidate)
        return normalized

    @field_validator("headers", mode="before")
    @classmethod
    def _normalize_headers(cls, value: Any) -> dict[str, str]:
        if value is None:
            return {}
        normalized: dict[str, str] = {}
        for key, candidate in dict(value).items():
            normalized[str(key)] = str(candidate)
        return normalized


class _BaseApiClient(Generic[ClientType]):
    """Shared logic between sync and async client variants."""

    _config: _ClientConfig
    _client: ClientType
    _owns_http_client: bool

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | URL | None = None,
        timeout: TimeoutTypes = DEFAULT_TIMEOUT_SECONDS,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        resolved_api_key = (api_key or os.getenv(API_KEY_ENV_VAR) or "").strip()
        if not resolved_api_key:
            msg = "API key was not provided and the PDFREST_API_KEY environment variable is not set."
            raise PdfRestConfigurationError(msg)

        default_headers: dict[str, str] = {
            "Authorization": f"Bearer {resolved_api_key}",
            "Accept": "application/json",
        }
        if headers:
            for key, value in headers.items():
                default_headers[str(key)] = str(value)

        resolved_base_url = (
            URL(str(base_url)) if base_url is not None else URL(DEFAULT_BASE_URL)
        )

        try:
            self._config = _ClientConfig(
                base_url=resolved_base_url,
                api_key=resolved_api_key,
                timeout=timeout,
                headers=default_headers,
            )
        except PdfRestConfigurationError:
            raise
        except ValidationError as exc:  # pragma: no cover - defensive
            raise PdfRestConfigurationError(str(exc)) from exc

    @property
    def base_url(self) -> URL:
        """Resolved base URL for the client."""

        return self._config.base_url

    def _prepare_request(
        self, method: HttpMethod, endpoint: str, options: RequestOptions | None = None
    ) -> _RequestModel:
        option_dict: dict[str, Any] = dict(options or {})
        combined_headers: dict[str, str] = dict(self._config.headers)
        if "headers" in option_dict and option_dict["headers"] is not None:
            combined_headers.update(
                {
                    str(key): str(value)
                    for key, value in cast(
                        Mapping[str, Any], option_dict["headers"]
                    ).items()
                }
            )

        params_dict: dict[str, str] | None = None
        if "params" in option_dict and option_dict["params"] is not None:
            raw_params = cast(Mapping[str, QueryParamValue], option_dict["params"])
            converted_params: dict[str, str] = {}
            for key, value in raw_params.items():
                if value is None:
                    continue
                converted_params[str(key)] = str(value)
            params_dict = converted_params if converted_params else None

        timeout_override = option_dict.get("timeout")
        timeout_value = (
            timeout_override if timeout_override is not None else self._config.timeout
        )

        try:
            request = _RequestModel(
                method=method,
                endpoint=endpoint,
                params=params_dict,
                headers=combined_headers,
                timeout=timeout_value,
            )
        except PdfRestConfigurationError:
            raise
        except ValidationError as exc:  # pragma: no cover - defensive
            raise PdfRestConfigurationError(str(exc)) from exc
        return request

    def _handle_response(self, response: httpx.Response) -> Any:
        if response.is_success:
            return self._decode_json(response)
        error_payload: Any = None
        message: str | None = None
        try:
            pdfrest_error = PdfRestErrorResponse.model_validate_json(response.content)
            message = pdfrest_error.error
        except ValidationError:
            error_payload = response.text
        raise PdfRestApiError(
            response.status_code, message=message, response_content=error_payload
        )

    def _decode_json(self, response: httpx.Response) -> Any:
        try:
            return response.json()
        except ValueError as exc:
            raise PdfRestApiError(
                response.status_code,
                message="Response body is not valid JSON.",
                response_content=response.text,
            ) from exc


class _SyncApiClient(_BaseApiClient[httpx.Client]):
    """Internal synchronous client implementation."""

    _client: httpx.Client

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | URL | None = None,
        timeout: TimeoutTypes = DEFAULT_TIMEOUT_SECONDS,
        headers: Mapping[str, str] | None = None,
        http_client: httpx.Client | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        super().__init__(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
            headers=headers,
        )
        self._owns_http_client = http_client is None
        self._client = http_client or httpx.Client(
            base_url=self.base_url,
            headers=dict(self._config.headers),
            timeout=self._config.timeout,
            transport=transport,
        )

    def close(self) -> None:
        if self._owns_http_client:
            self._client.close()

    def __enter__(self) -> _SyncApiClient:
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.close()

    def _send_request(self, request: _RequestModel) -> Any:
        http_client = self._client
        try:
            response = http_client.request(
                method=request.method,
                url=request.endpoint,
                params=request.params or None,
                headers=request.headers or None,
                timeout=request.timeout,
            )
        except httpx.HTTPError as exc:
            raise translate_httpx_error(exc) from exc
        return self._handle_response(response)


class _AsyncApiClient(_BaseApiClient[httpx.AsyncClient]):
    """Internal asynchronous client implementation."""

    _client: httpx.AsyncClient

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | URL | None = None,
        timeout: TimeoutTypes = DEFAULT_TIMEOUT_SECONDS,
        headers: Mapping[str, str] | None = None,
        http_client: httpx.AsyncClient | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        super().__init__(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
            headers=headers,
        )
        self._owns_http_client = http_client is None
        self._client = http_client or httpx.AsyncClient(
            base_url=self.base_url,
            headers=dict(self._config.headers),
            timeout=self._config.timeout,
            transport=transport,
        )

    async def aclose(self) -> None:
        if self._owns_http_client:
            await self._client.aclose()

    async def __aenter__(self) -> _AsyncApiClient:
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        await self.aclose()

    async def _send_request(self, request: _RequestModel) -> Any:
        http_client = self._client
        try:
            response = await http_client.request(
                method=request.method,
                url=request.endpoint,
                params=request.params or None,
                headers=request.headers or None,
                timeout=request.timeout,
            )
        except httpx.HTTPError as exc:
            raise translate_httpx_error(exc) from exc
        return self._handle_response(response)


class PdfRestClient(_SyncApiClient):
    """Synchronous client for interacting with the pdfrest API."""

    def __enter__(self) -> PdfRestClient:
        super().__enter__()
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        super().__exit__(exc_type, exc, traceback)

    def up(self, options: UpRequestOptions | None = None) -> UpResponse:
        """Call the `/up` health endpoint and return server metadata."""

        request = self._prepare_request("GET", "/up", options)
        payload = self._send_request(request)
        return UpResponse.model_validate(payload)


class AsyncPdfRestClient(_AsyncApiClient):
    """Asynchronous client for interacting with the pdfrest API."""

    async def __aenter__(self) -> AsyncPdfRestClient:
        await super().__aenter__()
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        await super().__aexit__(exc_type, exc, traceback)

    async def up(self, options: UpRequestOptions | None = None) -> UpResponse:
        """Call the `/up` health endpoint asynchronously and return server metadata."""

        request = self._prepare_request("GET", "/up", options)
        payload = await self._send_request(request)
        return UpResponse.model_validate(payload)
