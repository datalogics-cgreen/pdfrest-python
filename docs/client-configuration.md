# Client configuration

This guide explains how to configure
[`PdfRestClient`](api-reference.md#pdfrest.PdfRestClient) and
[`AsyncPdfRestClient`](api-reference.md#pdfrest.AsyncPdfRestClient), including
how SDK settings map to HTTPX behavior.

## Constructor parameters

Both clients support a shared baseline:

- `api_key`: API key used for the `Api-Key` header. If omitted, the SDK reads
  `PDFREST_API_KEY` from the environment.
- `base_url`: API host (defaults to `https://api.pdfrest.com`).
- `timeout`: `float` seconds or an
  [`httpx.Timeout`](https://www.python-httpx.org/api/#timeout) object.
- `headers`: default headers merged into every request.
- `max_retries`: retry count for retryable transport/timeouts and retryable
  HTTP status responses.

Sync-only options ([`PdfRestClient`](api-reference.md#pdfrest.PdfRestClient)):

- `http_client`: preconfigured
  [`httpx.Client`](https://www.python-httpx.org/api/#client) instance to reuse.
- `transport`: custom
  [`httpx.BaseTransport`](https://www.python-httpx.org/advanced/transports/).

Async-only options
([`AsyncPdfRestClient`](api-reference.md#pdfrest.AsyncPdfRestClient)):

- `http_client`: preconfigured
  [`httpx.AsyncClient`](https://www.python-httpx.org/api/#asyncclient) instance
  to reuse.
- `transport`: custom
  [`httpx.AsyncBaseTransport`](https://www.python-httpx.org/advanced/transports/).
- `concurrency_limit`: controls async file-info fetch fanout in multi-file
  operations.

## Timeout configuration

By default, the SDK uses an HTTPX timeout profile with a longer read timeout.
You can override with either a single float or a full timeout object:

```python
import httpx
from pdfrest import PdfRestClient

with PdfRestClient(
    timeout=httpx.Timeout(connect=5.0, read=180.0, write=30.0, pool=10.0)
) as client:
    status = client.up()
```

HTTPX references:

- [Timeouts](https://www.python-httpx.org/advanced/timeouts/)
- [API reference: `httpx.Timeout`](https://www.python-httpx.org/api/)

## Using a custom HTTPX client

If you need advanced HTTP behavior (custom TLS, proxies, limits, event hooks,
or a shared connection pool), provide a preconfigured HTTPX client.

```python
import httpx
from pdfrest import PdfRestClient

http_client = httpx.Client(
    timeout=httpx.Timeout(20.0),
    limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
)

with PdfRestClient(http_client=http_client) as client:
    response = client.up()
```

HTTPX references:

- [Clients](https://www.python-httpx.org/advanced/clients/)
- [Resource Limits](https://www.python-httpx.org/advanced/resource-limits/)
- [Proxies](https://www.python-httpx.org/advanced/proxies/)
- [SSL](https://www.python-httpx.org/advanced/ssl/)
- [Event Hooks](https://www.python-httpx.org/advanced/event-hooks/)

## Using a custom transport

For low-level customization (for example test transports and custom routing),
pass `transport=...`:

```python
import httpx
from pdfrest import PdfRestClient

transport = httpx.HTTPTransport(retries=0)

with PdfRestClient(transport=transport) as client:
    response = client.up()
```

HTTPX reference:

- [Transports](https://www.python-httpx.org/advanced/transports/)

## Default and per-request headers

`headers=` on the client sets default headers for all calls. Endpoint methods
also accept `extra_headers=` to override or add request-specific headers.

```python
from pdfrest import PdfRestClient

with PdfRestClient(headers={"X-App-Name": "my-service"}) as client:
    info = client.up(extra_headers={"X-Request-ID": "req-123"})
```

## Per-call request overrides

Most endpoint helpers on `PdfRestClient` and `AsyncPdfRestClient` accept the
same request-affecting keyword arguments so you can tune one call without
changing client-wide configuration.

| Argument | Type | Purpose | Default |
| --- | --- | --- | --- |
| `extra_query` | `Query \| None` | Additional query parameters merged into the request URL. | `None` |
| `extra_headers` | `AnyMapping \| None` | Additional HTTP headers merged into the request headers. | `None` |
| `extra_body` | `Body \| None` | Additional request body fields merged into JSON payloads. | `None` |
| `timeout` | `TimeoutTypes \| None` | Per-call timeout override (float seconds or `httpx.Timeout`). | `None` |

Behavior notes:

- `timeout=None` means “use the client default timeout profile.”
- `extra_headers` values override same-name default headers for that request.
- `extra_query` is merged with method-provided query params.
- `extra_body` is merged only for JSON requests.
  For multipart/form-data endpoint calls, `extra_body` is rejected by the SDK.

Example:

```python
from pdfrest import PdfRestClient

with PdfRestClient() as client:
    result = client.query_pdf_info(
        file=my_file,
        extra_query={"trace": "true"},
        extra_headers={"X-Request-ID": "req-123"},
        timeout=30.0,
    )
```

## `no-id-prefix` header

pdfRest supports a `no-id-prefix: true` request header used for
pdfAssistant compatibility. When enabled, generated IDs omit the leading
numeric prefix and return a plain UUIDv4 string.

### How to enable it

Set it as a default client header or per-request `extra_headers`:

```python
from pdfrest import PdfRestClient

with PdfRestClient(headers={"no-id-prefix": "true"}) as client:
    uploaded = client.files.create_from_paths(["./input.pdf"])
```

### Effect on `PdfRestFileID`

[`PdfRestFileID`](api-reference.md#pdfrest.models.PdfRestFileID) accepts both
forms:

- prefixed: `1<uuid-v4>` or `2<uuid-v4>` (37 chars)
- no prefix: `<uuid-v4>` (36 chars)

When `no-id-prefix` is enabled, returned IDs are the 36-character no-prefix
variant. In that case:

- `file_id.prefix` is `None`
- `file_id.uuid` is still the UUID portion

This means existing SDK code that uses
[`PdfRestFileID`](api-reference.md#pdfrest.models.PdfRestFileID) remains
compatible with either server ID format.
