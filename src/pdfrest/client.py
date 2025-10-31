"""Sync and async client interfaces for the pdfrest API."""

from __future__ import annotations

import asyncio
import importlib.metadata
import json
import os
import uuid
from collections.abc import AsyncIterator, Iterator, Mapping, Sequence
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
from .models import (
    PdfRestErrorResponse,
    PdfRestFile,
    PdfRestFileBasedResponse,
    PdfRestFileID,
    UpResponse,
)

__all__ = ("AsyncPdfRestClient", "PdfRestClient")

from .models._internal import ConvertToGraphic, PdfRestRawFileResponse, UploadURLs

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
UploadFiles = Sequence[FileTypes] | FileTypes

FilePath = str | PathLike[str]
FilePathTuple2 = tuple[FilePath, str | None]
FilePathTuple3 = tuple[FilePath, str | None, Mapping[str, str]]
FilePathTypes = FilePath | FilePathTuple2 | FilePathTuple3
FilePathInput = FilePathTypes | Sequence[FilePathTypes]
UrlValue = str | URL
UrlInput = UrlValue | Sequence[UrlValue]
NormalizedFileTypes: TypeAlias = FileContent | FileTuple2 | FileTuple3 | FileTuple4
DestinationPath = str | PathLike[str]


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
    if isinstance(files, Mapping):
        msg = "Upload files must be provided as a sequence or a single file specification."
        raise TypeError(msg)

    if isinstance(files, Sequence) and not isinstance(files, (str, bytes, bytearray)):
        items = list(files)
    else:
        # Treat single file specification as a one-element sequence.
        items = [cast(FileTypes, files)]

    if not items:
        msg = "At least one file must be provided."
        raise ValueError(msg)
    normalized_items: list[tuple[str, NormalizedFileTypes]] = []
    for file_value in items:
        normalized_items.append(
            (FILE_UPLOAD_FIELD_NAME, _normalize_file_type(cast(FileTypes, file_value)))
        )
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


def _normalize_path_inputs(
    file_paths: FilePathInput,
) -> list[FilePathTypes]:
    if isinstance(file_paths, Sequence) and not isinstance(
        file_paths, (str, bytes, bytearray)
    ):
        sequence_paths = cast(Sequence[FilePathTypes], file_paths)
        items: list[FilePathTypes] = list(sequence_paths)
    else:
        items = [cast(FilePathTypes, file_paths)]
    if not items:
        msg = "At least one file path must be provided."
        raise ValueError(msg)
    return items


def _resolve_file_id(file_ref: PdfRestFile | str) -> str:
    return file_ref.id if isinstance(file_ref, PdfRestFile) else str(file_ref)


def _normalize_file_id(file_ref: PdfRestFileID | str) -> PdfRestFileID:
    if isinstance(file_ref, PdfRestFileID):
        return file_ref
    return PdfRestFileID(str(file_ref))


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

        version = importlib.metadata.version("pdfrest")
        default_headers: dict[str, str] = {
            "Accept": "application/json",
            "wsn": "pdfrest-python",
            "User-Agent": f"pdfrest-python-sdk/{version}",
        }
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

    def download_file(self, file_id: str) -> httpx.Response:
        request = self._client.build_request("GET", f"/resource/{file_id}")
        try:
            response = self._client.send(request, stream=True)
        except httpx.HTTPError as exc:
            raise translate_httpx_error(exc) from exc
        if not response.is_success:
            try:
                self._handle_response(response)
            finally:
                response.close()
        return response

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

    async def download_file(self, file_id: str) -> httpx.Response:
        request = self._client.build_request("GET", f"/resource/{file_id}")
        try:
            response = await self._client.send(request, stream=True)
        except httpx.HTTPError as exc:
            raise translate_httpx_error(exc) from exc
        if not response.is_success:
            try:
                self._handle_response(response)
            finally:
                await response.aclose()
        return response

    async def fetch_file_info(self, file_id: str) -> PdfRestFile:
        request = self.prepare_request(
            "GET",
            f"/resource/{file_id}",
            query={"format": "info"},
        )
        payload = await self._send_request(request)
        return PdfRestFile.model_validate(payload)


class PdfRestFileStream:
    """Streaming wrapper for synchronously downloading files from pdfRest."""

    def __init__(self, response: httpx.Response) -> None:
        self._response = response

    def iter_bytes(self, chunk_size: int | None = None) -> Iterator[bytes]:
        yield from self._response.iter_bytes(chunk_size)

    def iter_text(self, chunk_size: int | None = None) -> Iterator[str]:
        yield from self._response.iter_text(chunk_size)

    def iter_lines(self) -> Iterator[str]:
        yield from self._response.iter_lines()

    def iter_raw(self, chunk_size: int | None = None) -> Iterator[bytes]:
        yield from self._response.iter_raw(chunk_size)

    def close(self) -> None:
        self._response.close()

    def __enter__(self) -> PdfRestFileStream:
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.close()


class AsyncPdfRestFileStream:
    """Streaming wrapper for asynchronously downloading files from pdfRest."""

    def __init__(self, response: httpx.Response) -> None:
        self._response = response

    async def iter_bytes(self, chunk_size: int | None = None) -> AsyncIterator[bytes]:
        async for chunk in self._response.aiter_bytes(chunk_size):
            yield chunk

    async def iter_text(self, chunk_size: int | None = None) -> AsyncIterator[str]:
        async for chunk in self._response.aiter_text(chunk_size):
            yield chunk

    async def iter_lines(self) -> AsyncIterator[str]:
        async for line in self._response.aiter_lines():
            yield line

    async def iter_raw(self, chunk_size: int | None = None) -> AsyncIterator[bytes]:
        async for chunk in self._response.aiter_raw(chunk_size):
            yield chunk

    async def close(self) -> None:
        await self._response.aclose()

    async def __aenter__(self) -> AsyncPdfRestFileStream:
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        await self.close()


class _FilesClient:
    """Expose file-related operations for the synchronous client."""

    def __init__(self, client: _SyncApiClient) -> None:
        self._client = client

    def get(self, file_ref: PdfRestFileID | str) -> PdfRestFile:
        """Retrieve file metadata given a file identifier."""
        file_id = _normalize_file_id(file_ref)
        return self._client.fetch_file_info(str(file_id))

    def create(self, files: UploadFiles) -> list[PdfRestFile]:
        """Upload one or more files by content.

        Provide either a single file specification or a sequence of file
        specifications (each matching the shapes accepted by httpx). Every
        uploaded part is sent using the field name ``file``.
        """
        normalized_files = _normalize_upload_files(files)
        request = self._client.prepare_request(
            "POST", "/upload", files=normalized_files
        )
        payload = self._client.send_request(request)
        file_ids = _extract_uploaded_file_ids(payload)
        return [self._client.fetch_file_info(file_id) for file_id in file_ids]

    def create_from_paths(self, file_paths: FilePathInput) -> list[PdfRestFile]:
        """Upload one or more files by their path.

        Each entry may be a bare path-like object or a tuple of
        `(path, content_type)` / `(path, content_type, headers)` where headers
        mirrors the httpx multipart header mapping. All opened file handles are
        closed once the request completes.
        """
        normalized_paths = _normalize_path_inputs(file_paths)

        with ExitStack() as stack:
            upload_specs: list[FileTypes] = []
            for spec in normalized_paths:
                path, content_type, headers = _parse_path_spec(spec)
                file_obj = stack.enter_context(path.open("rb"))
                filename = path.name
                if headers:
                    upload_specs.append((filename, file_obj, content_type, headers))
                elif content_type is not None:
                    upload_specs.append((filename, file_obj, content_type))
                else:
                    upload_specs.append((filename, file_obj))
            return self.create(upload_specs)

    def create_from_urls(self, urls: UrlInput) -> list[PdfRestFile]:
        """Upload one or more files by providing remote URLs."""

        normalized_urls = UploadURLs.model_validate({"url": urls})  # pyright: ignore[reportPrivateUsage]
        request = self._client.prepare_request(
            "POST",
            "/upload",
            json_body=normalized_urls.model_dump(mode="json"),
        )
        payload = self._client.send_request(request)
        file_ids = _extract_uploaded_file_ids(payload)
        return [self._client.fetch_file_info(file_id) for file_id in file_ids]

    def read_bytes(self, file_ref: PdfRestFile | str) -> bytes:
        response = self._client.download_file(_resolve_file_id(file_ref))
        try:
            return response.read()
        finally:
            response.close()

    def read_text(
        self,
        file_ref: PdfRestFile | str,
        *,
        encoding: str = "utf-8",
    ) -> str:
        response = self._client.download_file(_resolve_file_id(file_ref))
        try:
            response.encoding = encoding
            data = response.read()
            codec = response.encoding or encoding or "utf-8"
            return data.decode(codec)
        finally:
            response.close()

    def read_json(self, file_ref: PdfRestFile | str) -> Any:
        response = self._client.download_file(_resolve_file_id(file_ref))
        try:
            data = response.read()
            codec = response.encoding or "utf-8"
            return json.loads(data.decode(codec))
        finally:
            response.close()

    def write_bytes(
        self,
        file_ref: PdfRestFile | str,
        destination: DestinationPath,
    ) -> Path:
        response = self._client.download_file(_resolve_file_id(file_ref))
        path = Path(destination)
        try:
            with path.open("wb") as file_handle:
                for chunk in response.iter_bytes():
                    file_handle.write(chunk)
        finally:
            response.close()
        return path

    def stream(self, file_ref: PdfRestFile | str) -> PdfRestFileStream:
        response = self._client.download_file(_resolve_file_id(file_ref))
        return PdfRestFileStream(response)


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

    async def get(self, file_ref: PdfRestFileID | str) -> PdfRestFile:
        """Retrieve file metadata given a file identifier."""
        file_id = _normalize_file_id(file_ref)
        return await self._client.fetch_file_info(str(file_id))

    async def create(self, files: UploadFiles) -> list[PdfRestFile]:
        """Upload one or more files by content.

        Provide either a single file specification or a sequence of file
        specifications (each matching the shapes accepted by httpx). Every
        uploaded part is sent using the field name ``file``.
        """
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

    async def create_from_paths(self, file_paths: FilePathInput) -> list[PdfRestFile]:
        """Upload one or more files by their path.

        Each entry may be a bare path-like object or a tuple of
        `(path, content_type)` / `(path, content_type, headers)` where headers
        mirrors the httpx multipart header mapping. All opened file handles are
        closed once the request completes.
        """
        normalized_paths = _normalize_path_inputs(file_paths)

        with ExitStack() as stack:
            upload_specs: list[FileTypes] = []
            for spec in normalized_paths:
                path, content_type, headers = _parse_path_spec(spec)
                file_obj = stack.enter_context(path.open("rb"))
                filename = path.name
                if headers:
                    upload_specs.append((filename, file_obj, content_type, headers))
                elif content_type is not None:
                    upload_specs.append((filename, file_obj, content_type))
                else:
                    upload_specs.append((filename, file_obj))
            return await self.create(upload_specs)

    async def create_from_urls(self, urls: UrlInput) -> list[PdfRestFile]:
        """Upload one or more files by providing remote URLs."""

        normalized_urls = UploadURLs.model_validate({"url": urls})
        request = self._client.prepare_request(
            "POST",
            "/upload",
            json_body=normalized_urls.model_dump(mode="json"),
        )
        payload = await self._client.send_request(request)
        file_ids = _extract_uploaded_file_ids(payload)
        semaphore = asyncio.Semaphore(self._concurrency_limit)

        async def fetch(file_id: str) -> PdfRestFile:
            async with semaphore:
                return await self._client.fetch_file_info(file_id)

        return await asyncio.gather(*(fetch(file_id) for file_id in file_ids))

    async def read_bytes(self, file_ref: PdfRestFile | str) -> bytes:
        response = await self._client.download_file(_resolve_file_id(file_ref))
        try:
            return await response.aread()
        finally:
            await response.aclose()

    async def read_text(
        self,
        file_ref: PdfRestFile | str,
        *,
        encoding: str = "utf-8",
    ) -> str:
        response = await self._client.download_file(_resolve_file_id(file_ref))
        try:
            response.encoding = encoding
            data = await response.aread()
            codec = response.encoding or encoding or "utf-8"
            return data.decode(codec)
        finally:
            await response.aclose()

    async def read_json(self, file_ref: PdfRestFile | str) -> Any:
        response = await self._client.download_file(_resolve_file_id(file_ref))
        try:
            data = await response.aread()
            codec = response.encoding or "utf-8"
            return json.loads(data.decode(codec))
        finally:
            await response.aclose()

    async def write_bytes(
        self,
        file_ref: PdfRestFile | str,
        destination: DestinationPath,
    ) -> Path:
        response = await self._client.download_file(_resolve_file_id(file_ref))
        path = Path(destination)
        try:
            with path.open("wb") as file_handle:
                async for chunk in response.aiter_bytes():
                    file_handle.write(chunk)
        finally:
            await response.aclose()
        return path

    async def stream(self, file_ref: PdfRestFile | str) -> AsyncPdfRestFileStream:
        response = await self._client.download_file(_resolve_file_id(file_ref))
        return AsyncPdfRestFileStream(response)


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

    def convert_to_png(
        self,
        files: PdfRestFile | Sequence[PdfRestFile],
        *,
        output_prefix: str | None = None,
        page_range: str | Sequence[str] | None = None,
        resolution: int = 300,
        color_model: Literal["rgb", "rgba", "gray"] = "rgb",
        smoothing: Literal["none", "all", "text", "line", "image"]
        | Sequence[Literal["none", "all", "text", "line", "image"]]
        | None = None,
    ) -> PdfRestFileBasedResponse:
        """Convert one or more pdfRest files to PNG images."""

        payload: dict[str, Any] = {
            "files": files,
            "resolution": resolution,
            "color_model": color_model,
        }
        if output_prefix is not None:
            payload["output_prefix"] = output_prefix
        if page_range is not None:
            payload["page_range"] = page_range
        if smoothing is not None:
            payload["smoothing"] = smoothing

        conversion_options = ConvertToGraphic.model_validate(payload)
        request = self.prepare_request(
            "POST",
            "/png",
            json_body=conversion_options.model_dump(
                mode="json", by_alias=True, exclude_none=True, exclude_defaults=True
            ),
        )
        raw_payload = self._send_request(request)
        raw_response = PdfRestRawFileResponse.model_validate(raw_payload)

        output_ids = raw_response.ids or []
        output_files = [self.fetch_file_info(str(file_id)) for file_id in output_ids]

        return PdfRestFileBasedResponse.model_validate(
            {
                "input_id": [str(file_id) for file_id in raw_response.input_id],
                "output_file": [
                    file.model_dump(mode="json", by_alias=True) for file in output_files
                ],
                "warning": raw_response.warning,
            }
        )


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

    async def convert_to_png(
        self,
        files: PdfRestFile | Sequence[PdfRestFile],
        *,
        output_prefix: str | None = None,
        page_range: str | Sequence[str] | None = None,
        resolution: int = 300,
        color_model: Literal["rgb", "rgba", "gray"] = "rgb",
        smoothing: Literal["none", "all", "text", "line", "image"]
        | Sequence[Literal["none", "all", "text", "line", "image"]]
        | None = None,
    ) -> PdfRestFileBasedResponse:
        """Asynchronously convert one or more pdfRest files to PNG images."""

        payload: dict[str, Any] = {
            "files": files,
            "resolution": resolution,
            "color_model": color_model,
        }
        if output_prefix is not None:
            payload["output_prefix"] = output_prefix
        if page_range is not None:
            payload["page_range"] = page_range
        if smoothing is not None:
            payload["smoothing"] = smoothing

        conversion_options = ConvertToGraphic.model_validate(payload)
        request = self.prepare_request(
            "POST",
            "/png",
            json_body=conversion_options.model_dump(
                mode="json", by_alias=True, exclude_none=True, exclude_unset=True
            ),
        )
        raw_payload = await self._send_request(request)
        raw_response = PdfRestRawFileResponse.model_validate(raw_payload)

        output_ids = raw_response.ids or []
        output_files: list[PdfRestFile] = []
        if output_ids:
            output_files = list(
                await asyncio.gather(
                    *(self.fetch_file_info(str(file_id)) for file_id in output_ids)
                )
            )

        return PdfRestFileBasedResponse.model_validate(
            {
                "input_id": [str(file_id) for file_id in raw_response.input_id],
                "output_file": [
                    file.model_dump(mode="json", by_alias=True) for file in output_files
                ],
                "warning": raw_response.warning,
            }
        )
