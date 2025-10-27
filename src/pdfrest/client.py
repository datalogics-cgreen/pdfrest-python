"""Sync and async client interfaces for the pdfrest API."""

from __future__ import annotations

import os
import uuid
from collections.abc import Mapping
from typing import Any, Generic, Literal, TypeVar

import httpx
from httpx import URL
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from .exceptions import (
    PdfRestApiError,
    PdfRestAuthenticationError,
    PdfRestConfigurationError,
    translate_httpx_error,
)
from .models import PdfRestErrorResponse, UpResponse

__all__ = ("AsyncPdfRestClient", "PdfRestClient")

DEFAULT_BASE_URL = "https://api.pdfrest.com"
API_KEY_ENV_VAR = "PDFREST_API_KEY"
API_KEY_HEADER_NAME = "Api-Key"
DEFAULT_TIMEOUT_SECONDS = 10.0

HttpMethod = Literal["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"]
QueryParamValue = str | int | float | bool | None
TimeoutTypes = float | httpx.Timeout | None
AnyMapping = Mapping[str, Any]
Query = Mapping[str, QueryParamValue]
Body = Mapping[str, Any]


ClientType = TypeVar("ClientType", httpx.Client, httpx.AsyncClient)


class _ClientConfig(BaseModel):
    """Internal representation of client configuration validated by Pydantic."""

    base_url: URL
    api_key: str | None = None
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
    def _validate_api_key(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        if not trimmed:
            return None
        return trimmed

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
    params: dict[str, QueryParamValue] | None = None
    headers: dict[str, str] = Field(default_factory=dict)
    timeout: TimeoutTypes
    json_body: dict[str, Any] | None = None

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @field_validator("endpoint")
    @classmethod
    def _validate_endpoint(cls, value: str) -> str:
        if not value.startswith("/"):
            msg = "endpoint must start with '/'."
            raise PdfRestConfigurationError(msg)
        return value


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
        headers: AnyMapping | None = None,
    ) -> None:
        raw_api_key = api_key if api_key is not None else os.getenv(API_KEY_ENV_VAR)
        resolved_api_key = (
            raw_api_key.strip() if raw_api_key and raw_api_key.strip() else None
        )

        resolved_base_url = (
            URL(str(base_url)) if base_url is not None else URL(DEFAULT_BASE_URL)
        )

        if resolved_api_key is None and self._base_url_requires_api_key(
            resolved_base_url
        ):
            msg = (
                "API key is required when communicating with pdfRest-hosted "
                "endpoints. Provide `api_key` or set the PDFREST_API_KEY environment variable."
            )
            raise PdfRestConfigurationError(msg)

        if resolved_api_key is not None:
            self._validate_pdfrest_api_key(resolved_api_key, resolved_base_url)

        default_headers: dict[str, str] = {"Accept": "application/json"}
        if resolved_api_key is not None:
            default_headers[API_KEY_HEADER_NAME] = resolved_api_key
        if headers:
            for key, value in headers.items():
                default_headers[str(key)] = str(value)

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

    @staticmethod
    def _base_url_requires_api_key(url: URL) -> bool:
        host = url.host or ""
        return host.lower().endswith("pdfrest.com")

    @staticmethod
    def _validate_pdfrest_api_key(api_key: str, url: URL) -> None:
        if not _BaseApiClient._base_url_requires_api_key(url):
            return
        if len(api_key) != 36:
            msg = "pdfRest API keys must be 36 characters (UUID format)."
            raise PdfRestConfigurationError(msg)
        try:
            uuid.UUID(api_key)
        except ValueError:
            msg = "pdfRest API keys must be valid UUID strings."
            raise PdfRestConfigurationError(msg) from None

    @property
    def base_url(self) -> URL:
        """Resolved base URL for the client."""

        return self._config.base_url

    def _prepare_request(
        self,
        method: HttpMethod,
        endpoint: str,
        *,
        query: Query | None = None,
        json_body: Body | None = None,
        extra_query: Query | None = None,
        extra_headers: AnyMapping | None = None,
        extra_body: Body | None = None,
        timeout: TimeoutTypes | None = None,
    ) -> _RequestModel:
        headers = self._compose_headers(extra_headers)
        params = self._compose_query_params(query, extra_query)
        json_payload = self._compose_json_body(json_body, extra_body)
        timeout_value = timeout if timeout is not None else self._config.timeout

        try:
            request = _RequestModel(
                method=method,
                endpoint=endpoint,
                params=params,
                headers=headers,
                timeout=timeout_value,
                json_body=json_payload,
            )
        except PdfRestConfigurationError:
            raise
        except ValidationError as exc:  # pragma: no cover - defensive
            raise PdfRestConfigurationError(str(exc)) from exc
        return request

    def _compose_headers(self, extra_headers: AnyMapping | None) -> dict[str, str]:
        combined_headers: dict[str, str] = dict(self._config.headers)
        if extra_headers is None:
            return combined_headers
        for key, value in extra_headers.items():
            combined_headers[str(key)] = str(value)
        return combined_headers

    @staticmethod
    def _compose_query_params(
        query: Query | None,
        extra_query: Query | None,
    ) -> dict[str, QueryParamValue] | None:
        params: dict[str, QueryParamValue] = {}
        for mapping in (query, extra_query):
            if mapping is None:
                continue
            for key, value in mapping.items():
                params[str(key)] = value
        return params or None

    @staticmethod
    def _compose_json_body(
        json_body: Body | None,
        extra_body: Body | None,
    ) -> dict[str, Any] | None:
        if json_body is None:
            if extra_body is not None:
                msg = "extra_body can only be used with JSON requests."
                raise PdfRestConfigurationError(msg)
            return None
        payload: dict[str, Any] = dict(json_body)
        if extra_body is not None:
            for key, value in extra_body.items():
                payload[str(key)] = value
        return payload

    def _handle_response(self, response: httpx.Response) -> Any:
        if response.is_success:
            return self._decode_json(response)

        message, error_payload = self._extract_error_details(response)

        if response.status_code == 401:
            auth_message = message or "Authentication with pdfRest failed."
            raise PdfRestAuthenticationError(
                response.status_code,
                message=auth_message,
                response_content=error_payload,
            )

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

    @staticmethod
    def _extract_error_details(
        response: httpx.Response,
    ) -> tuple[str | None, Any | None]:
        try:
            pdfrest_error = PdfRestErrorResponse.model_validate_json(response.content)
        except ValidationError:
            return None, response.text
        return pdfrest_error.error, None


class _SyncApiClient(_BaseApiClient[httpx.Client]):
    """Internal synchronous client implementation."""

    _client: httpx.Client

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | URL | None = None,
        timeout: TimeoutTypes = DEFAULT_TIMEOUT_SECONDS,
        headers: AnyMapping | None = None,
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
                json=request.json_body,
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
        headers: AnyMapping | None = None,
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
                json=request.json_body,
            )
        except httpx.HTTPError as exc:
            raise translate_httpx_error(exc) from exc
        return self._handle_response(response)


class PdfRestClient(_SyncApiClient):
    """Synchronous client for interacting with the pdfrest API."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | URL | None = None,
        timeout: TimeoutTypes = DEFAULT_TIMEOUT_SECONDS,
        headers: AnyMapping | None = None,
        http_client: httpx.Client | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        """Create a synchronous pdfRest client."""

        super().__init__(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
            headers=headers,
            http_client=http_client,
            transport=transport,
        )

    def __enter__(self) -> PdfRestClient:
        super().__enter__()
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        super().__exit__(exc_type, exc, traceback)

    def up(
        self,
        *,
        extra_headers: AnyMapping | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: TimeoutTypes | None = None,
    ) -> UpResponse:
        """Call the `/up` health endpoint and return server metadata."""

        request = self._prepare_request(
            "GET",
            "/up",
            extra_headers=extra_headers,
            extra_query=extra_query,
            extra_body=extra_body,
            timeout=timeout,
        )
        payload = self._send_request(request)
        return UpResponse.model_validate(payload)


class AsyncPdfRestClient(_AsyncApiClient):
    """Asynchronous client for interacting with the pdfrest API."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | URL | None = None,
        timeout: TimeoutTypes = DEFAULT_TIMEOUT_SECONDS,
        headers: AnyMapping | None = None,
        http_client: httpx.AsyncClient | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        """Create an asynchronous pdfRest client."""

        super().__init__(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
            headers=headers,
            http_client=http_client,
            transport=transport,
        )

    async def __aenter__(self) -> AsyncPdfRestClient:
        await super().__aenter__()
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        await super().__aexit__(exc_type, exc, traceback)

    async def up(
        self,
        *,
        extra_headers: AnyMapping | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: TimeoutTypes | None = None,
    ) -> UpResponse:
        """Call the `/up` health endpoint asynchronously and return server metadata."""

        request = self._prepare_request(
            "GET",
            "/up",
            extra_headers=extra_headers,
            extra_query=extra_query,
            extra_body=extra_body,
            timeout=timeout,
        )
        payload = await self._send_request(request)
        return UpResponse.model_validate(payload)
