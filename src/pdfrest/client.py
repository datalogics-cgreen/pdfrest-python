"""Sync and async client interfaces for the pdfrest API."""

from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import Mapping, Sequence
from contextlib import ExitStack
from os import PathLike
from pathlib import Path
from typing import IO, Any, Generic, Literal, TypeAlias, TypeVar, cast

import httpx
from httpx import URL
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from .exceptions import (
    PdfRestApiError,
    PdfRestAuthenticationError,
    PdfRestConfigurationError,
    translate_httpx_error,
)
from .models import PdfRestErrorResponse, PdfRestFile, UpResponse

__all__ = ("AsyncPdfRestClient", "PdfRestClient")

DEFAULT_BASE_URL = "https://api.pdfrest.com"
API_KEY_ENV_VAR = "PDFREST_API_KEY"
API_KEY_HEADER_NAME = "Api-Key"
DEFAULT_TIMEOUT_SECONDS = 10.0
FILE_UPLOAD_FIELD_NAME = "file"
DEFAULT_FILE_INFO_CONCURRENCY = 8

HttpMethod = Literal["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"]
QueryParamValue = str | int | float | bool | None
TimeoutTypes = float | httpx.Timeout | None
AnyMapping = Mapping[str, Any]
Query = Mapping[str, QueryParamValue]
Body = Mapping[str, Any]

FileContent = IO[bytes] | bytes | str
FileTuple2 = tuple[str | None, FileContent]
FileTuple3 = tuple[str | None, FileContent, str | None]
FileTuple4 = tuple[str | None, FileContent, str | None, Mapping[str, str]]
FileTypes = FileContent | FileTuple2 | FileTuple3 | FileTuple4
UploadFiles = Mapping[str, FileTypes] | Sequence[tuple[str, FileTypes]]

FilePath = str | PathLike[str]
FilePathTuple2 = tuple[FilePath, str | None]
FilePathTuple3 = tuple[FilePath, str | None, Mapping[str, str]]
FilePathTypes = FilePath | FilePathTuple2 | FilePathTuple3
NormalizedFileTypes: TypeAlias = FileContent | FileTuple2 | FileTuple3 | FileTuple4


def _extract_uploaded_file_ids(payload: Any) -> list[str]:
    try:
        files_payload = payload["files"]
    except (TypeError, KeyError) as exc:  # pragma: no cover - defensive
        raise PdfRestApiError(
            500, message="Upload response missing 'files' collection."
        ) from exc
    if not isinstance(files_payload, Sequence):  # pragma: no cover - defensive
        raise PdfRestApiError(500, message="Upload response 'files' is not a sequence.")
    entries = cast(Sequence[Mapping[str, Any]], files_payload)
    file_ids: list[str] = []
    for entry in entries:
        if "id" not in entry:
            raise PdfRestApiError(
                500, message="Upload response contains invalid file references."
            )
        file_ids.append(str(entry["id"]))
    return file_ids


def _normalize_headers(headers: Mapping[str, str]) -> Mapping[str, str]:
    return {str(key): str(value) for key, value in headers.items()}


def _ensure_file_content(value: FileContent) -> FileContent:
    if isinstance(value, (bytes, str)):
        return value
    if hasattr(value, "read"):
        return value
    msg = "File content must be a readable binary stream, bytes, or str."
    raise TypeError(msg)


def _normalize_file_type(file_value: FileTypes) -> NormalizedFileTypes:
    if isinstance(file_value, tuple):
        length = len(file_value)
        if length not in {2, 3, 4}:
            msg = "File tuple inputs must contain 2, 3, or 4 items."
            raise TypeError(msg)
        if length == 2:
            filename, content = cast(FileTuple2, file_value)
            normalized_filename = str(filename) if filename is not None else None
            normalized_content = _ensure_file_content(content)
            return (normalized_filename, normalized_content)
        if length == 3:
            filename, content, content_type = cast(FileTuple3, file_value)
            normalized_filename = str(filename) if filename is not None else None
            normalized_content = _ensure_file_content(content)
            normalized_content_type = (
                str(content_type) if content_type is not None else None
            )
            return (normalized_filename, normalized_content, normalized_content_type)

        filename, content, content_type, headers = cast(FileTuple4, file_value)
        normalized_filename = str(filename) if filename is not None else None
        normalized_content = _ensure_file_content(content)
        normalized_content_type = (
            str(content_type) if content_type is not None else None
        )
        if not isinstance(headers, Mapping):
            msg = "Headers must be provided as a mapping of str keys to str values."
            raise TypeError(msg)
        normalized_headers = _normalize_headers(headers)
        return (
            normalized_filename,
            normalized_content,
            normalized_content_type,
            normalized_headers,
        )
    return _ensure_file_content(file_value)


def _normalize_upload_files(
    files: UploadFiles,
) -> list[tuple[str, NormalizedFileTypes]]:
    is_mapping = isinstance(files, Mapping)
    if is_mapping:
        mapping_files = cast(Mapping[str, FileTypes], files)
        items: list[tuple[str, FileTypes]] = list(mapping_files.items())
    else:
        sequence_files = cast(Sequence[tuple[str, FileTypes]], files)
        items = list(sequence_files)
    if not items:
        msg = "At least one file must be provided."
        raise ValueError(msg)
    normalized_items: list[tuple[str, NormalizedFileTypes]] = []
    for entry in items:
        if is_mapping:
            field_name, file_value = entry
        else:
            if not isinstance(entry, tuple) or len(entry) != 2:
                msg = "Files sequence entries must be (field_name, file_value) tuples."
                raise TypeError(msg)
            field_name, file_value = entry
        normalized_items.append((str(field_name), _normalize_file_type(file_value)))
    return normalized_items


def _parse_path_spec(spec: FilePathTypes) -> tuple[Path, str | None, Mapping[str, str]]:
    if isinstance(spec, tuple):
        length = len(spec)
        if length == 2:
            raw_path, content_type = cast(FilePathTuple2, spec)
            headers: Mapping[str, str] = {}
        elif length == 3:
            raw_path, content_type, headers = cast(FilePathTuple3, spec)
            if not isinstance(headers, Mapping):
                msg = "Headers must be provided as a mapping of str keys to str values."
                raise TypeError(msg)
        else:
            msg = "File path tuples must contain a path plus optional content type and headers."
            raise TypeError(msg)
        normalized_headers = _normalize_headers(headers)
        normalized_content_type = (
            str(content_type) if content_type is not None else None
        )
        path = Path(raw_path)
        return path, normalized_content_type, normalized_headers
    path = Path(spec)
    return path, None, {}


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
    files: Any | None = None
    data: Any | None = None

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
        files: Any | None = None,
        data: Any | None = None,
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
                files=files,
                data=data,
            )
        except PdfRestConfigurationError:
            raise
        except ValidationError as exc:  # pragma: no cover - defensive
            raise PdfRestConfigurationError(str(exc)) from exc
        return request

    def prepare_request(
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
        files: Any | None = None,
        data: Any | None = None,
    ) -> _RequestModel:
        return self._prepare_request(
            method,
            endpoint,
            query=query,
            json_body=json_body,
            extra_query=extra_query,
            extra_headers=extra_headers,
            extra_body=extra_body,
            timeout=timeout,
            files=files,
            data=data,
        )

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
                files=request.files,
                data=request.data,
            )
        except httpx.HTTPError as exc:
            raise translate_httpx_error(exc) from exc
        return self._handle_response(response)

    def send_request(self, request: _RequestModel) -> Any:
        return self._send_request(request)

    def fetch_file_info(self, file_id: str) -> PdfRestFile:
        request = self.prepare_request(
            "GET",
            f"/resource/{file_id}",
            query={"format": "info"},
        )
        payload = self._send_request(request)
        return PdfRestFile.model_validate(payload)


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
                files=request.files,
                data=request.data,
            )
        except httpx.HTTPError as exc:
            raise translate_httpx_error(exc) from exc
        return self._handle_response(response)

    async def send_request(self, request: _RequestModel) -> Any:
        return await self._send_request(request)

    async def fetch_file_info(self, file_id: str) -> PdfRestFile:
        request = self.prepare_request(
            "GET",
            f"/resource/{file_id}",
            query={"format": "info"},
        )
        payload = await self._send_request(request)
        return PdfRestFile.model_validate(payload)


class _FilesClient:
    """Expose file-related operations for the synchronous client."""

    def __init__(self, client: _SyncApiClient) -> None:
        self._client = client

    def create(self, files: UploadFiles) -> list[PdfRestFile]:
        """Upload one or more files by content, in the same style accepted by
        the `files` parameter of `httpx.Client.post`.

        Provide either a mapping of field names to file specifications, or a
        sequence of `(field_name, file_spec)` tuples. File specifications may be
        raw file-like objects, bytes, str, or the tuple forms documented by
        httpx.
        """
        normalized_files = _normalize_upload_files(files)
        request = self._client.prepare_request(
            "POST", "/upload", files=normalized_files
        )
        payload = self._client.send_request(request)
        file_ids = _extract_uploaded_file_ids(payload)
        return [self._client.fetch_file_info(file_id) for file_id in file_ids]

    def create_from_paths(
        self, file_paths: Sequence[FilePathTypes]
    ) -> list[PdfRestFile]:
        """Upload one or more files by their path.

        Each entry may be a bare path-like object or a tuple of
        `(path, content_type)` / `(path, content_type, headers)` where headers
        mirrors the httpx multipart header mapping. All opened file handles are
        closed once the request completes.
        """
        if not file_paths:
            msg = "At least one file path must be provided."
            raise ValueError(msg)

        with ExitStack() as stack:
            upload_entries: list[tuple[str, FileTypes]] = []
            for spec in file_paths:
                path, content_type, headers = _parse_path_spec(spec)
                file_obj = stack.enter_context(path.open("rb"))
                filename = path.name
                if headers:
                    upload_entries.append(
                        (
                            FILE_UPLOAD_FIELD_NAME,
                            (filename, file_obj, content_type, headers),
                        )
                    )
                elif content_type is not None:
                    upload_entries.append(
                        (FILE_UPLOAD_FIELD_NAME, (filename, file_obj, content_type))
                    )
                else:
                    upload_entries.append(
                        (FILE_UPLOAD_FIELD_NAME, (filename, file_obj))
                    )
            return self.create(upload_entries)


class _AsyncFilesClient:
    """Expose file-related operations for the asynchronous client."""

    def __init__(
        self,
        client: _AsyncApiClient,
        *,
        concurrency_limit: int = DEFAULT_FILE_INFO_CONCURRENCY,
    ) -> None:
        self._client = client
        self._concurrency_limit = concurrency_limit

    async def create(self, files: UploadFiles) -> list[PdfRestFile]:
        """Upload one or more files by content, in the same style accepted by
        the `files` parameter of `httpx.AsyncClient.post`.

        Provide either a mapping of field names to file specifications, or a
        sequence of `(field_name, file_spec)` tuples. File specifications may be
        raw file-like objects, bytes, str, or the tuple forms documented by
        httpx."""
        normalized_files = _normalize_upload_files(files)
        request = self._client.prepare_request(
            "POST", "/upload", files=normalized_files
        )
        payload = await self._client.send_request(request)
        file_ids = _extract_uploaded_file_ids(payload)
        semaphore = asyncio.Semaphore(self._concurrency_limit)

        async def fetch(file_id: str) -> PdfRestFile:
            async with semaphore:
                return await self._client.fetch_file_info(file_id)

        return await asyncio.gather(*(fetch(file_id) for file_id in file_ids))

    async def create_from_paths(
        self, file_paths: Sequence[FilePathTypes]
    ) -> list[PdfRestFile]:
        """Upload one or more files by their path.

        Each entry may be a bare path-like object or a tuple of
        `(path, content_type)` / `(path, content_type, headers)` where headers
        mirrors the httpx multipart header mapping. All opened file handles are
        closed once the request completes.
        """
        if not file_paths:
            msg = "At least one file path must be provided."
            raise ValueError(msg)

        with ExitStack() as stack:
            upload_entries: list[tuple[str, FileTypes]] = []
            for spec in file_paths:
                path, content_type, headers = _parse_path_spec(spec)
                file_obj = stack.enter_context(path.open("rb"))
                filename = path.name
                if headers:
                    upload_entries.append(
                        (
                            FILE_UPLOAD_FIELD_NAME,
                            (filename, file_obj, content_type, headers),
                        )
                    )
                elif content_type is not None:
                    upload_entries.append(
                        (FILE_UPLOAD_FIELD_NAME, (filename, file_obj, content_type))
                    )
                else:
                    upload_entries.append(
                        (FILE_UPLOAD_FIELD_NAME, (filename, file_obj))
                    )
            return await self.create(upload_entries)


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
        self._files_client = _FilesClient(self)

    def __enter__(self) -> PdfRestClient:
        super().__enter__()
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        super().__exit__(exc_type, exc, traceback)

    @property
    def files(self) -> _FilesClient:
        return self._files_client

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
        self._files_client = _AsyncFilesClient(self)

    async def __aenter__(self) -> AsyncPdfRestClient:
        await super().__aenter__()
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        await super().__aexit__(exc_type, exc, traceback)

    @property
    def files(self) -> _AsyncFilesClient:
        return self._files_client

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
