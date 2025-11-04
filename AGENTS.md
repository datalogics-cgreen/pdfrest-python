# Repository Guidelines

## Project Structure & Module Organization

- Source lives in `src/pdfrest/`; expose public APIs via `__all__` and keep
  package metadata in `pyproject.toml`.
- Tests sit in `tests/` mirroring the module layout (e.g.,
  `tests/test_client.py`).
- Workflow definitions are in `.github/workflows/`; adjust only when CI
  requirements change.
- Documentation and contributor notes reside at the repo root (`README.md`,
  `AGENTS.md`). Automation sessions live in `noxfile.py`; keep shared task logic
  there.

## Build, Test, and Development Commands

- `uv sync --group dev` — create/update the virtual environment with lint,
  type-check, and test tooling.
- `uv run pre-commit run --all-files` — enforce formatting and lint rules before
  pushing.
- `uv run pytest` — execute the suite with the active interpreter.
- `uv build` — produce wheels and sdists identical to the release workflow.
- `uvx nox -s tests` — create matrix virtualenvs via nox and execute the pytest
  session.
- `nox` executes pytest sessions with built-in parallelism; when invoking pytest
  directly use `pytest -n 8 --maxschedchunk 2` to mirror the parallel test
  scheduling and keep runtimes predictable.

## Coding Style & Naming Conventions

- Target Python 3.10–3.14; use 4-space indentation and type hints for public
  APIs.
- Black + isort (via ruff) enforce formatting; run through pre-commit prior to
  review.
- Use `snake_case` for functions/modules, `PascalCase` for classes, and
  `UPPER_SNAKE_CASE` for constants.
- Prefer `pathlib`, f-strings, and other modern stdlib features—pyupgrade rules
  will flag legacy code.
- When calling pdfRest, supply the API key via the `Api-Key` header (not
  `Authorization: Bearer`); keep tests and client defaults in sync with this
  convention.
- Treat `PdfRestClient` and `AsyncPdfRestClient` as context managers in both
  production code and tests so transports are disposed deterministically.
- When uploading content, always send the multipart field name `file`; when
  uploading by URL, send a JSON payload using the `url` key with a list of
  http/https addresses (single values are promoted to lists internally).
- `prepare_request` rejects mixed multipart (`files`) and JSON payloads; only
  URL uploads (`create_from_urls`) should combine JSON bodies with the request.
- Replicate server-side safeguards when porting validation logic: the output
  prefix must stay basename-only, reject reserved names (`profile.json`,
  `metadata.json`), forbid leading dots or special characters, and report the
  offending characters in error messages. Page-range validation operates on each
  list item individually—accepts positive integers, `last`, or ranges like
  `1-3`/`6-last`—and must raise errors that match the front-end wording.
- Combine multiple synchronous context managers in a single `with` statement
  (ruff enforces `SIM117`). When an async context manager participates (e.g.,
  `async with AsyncPdfRestClient(...)`), nest any synchronous companions such as
  `pytest.raises` inside the async block—Python forbids mixing `async with` and
  regular `with` clauses in the same statement. When working with `HttpUrl`
  objects, cast to `str` before string operations such as suffix checks.
- For image conversions, adapt request data with `BasePdfRestGraphicPayload`
  generics; name concrete payloads `BmpPdfRestPayload`, `GifPdfRestPayload`,
  `JpegPdfRestPayload`, `PngPdfRestPayload`, and `TiffPdfRestPayload`. Client
  helpers should accept a `payload_model` argument and use fully spelled-out
  method names such as `convert_to_jpeg`/`convert_to_tiff` (avoid historic
  three-letter suffixes).
- When adding new services, provide per-endpoint test modules mirroring PNG’s
  coverage: parameterized successes for every allowed literal value, request
  customization (sync + async), validation failures, and multi-file guards. Add
  a shared validation suite when multiple endpoints rely on the same input rules
  (e.g., `tests/test_graphic_payload_validation.py`).
- Do not import from private modules (names beginning with an underscore) in
  tests or production code—expose any shared helpers via a public module first.

## Testing Guidelines

- Write pytest tests: files named `test_*.py`, test functions `test_*`, fixtures
  in `conftest.py` where shared.
- Ensure high-value coverage of public functions and edge cases; document intent
  in test docstrings when non-obvious.
- Use `uvx nox -s tests` to exercise the full interpreter matrix locally when
  validating compatibility.
- When writing live tests for URL uploads, first create the remote resources via
  `create_from_paths`, then reuse the returned URLs in `create_from_urls` to
  avoid relying on third-party availability.
- For parameterized tests prefer `pytest.param(..., id="short-label")` so test
  IDs stay readable; make assertions for every relevant response attribute (name
  prefix, MIME type, size, URLs, warnings).
- Always couple `pytest.raises` with an explicit `match=` regex that reflects
  the intended validation error wording—mirror the human-readable text rather
  than relying on default exception formatting.
- Mirror PNG’s request/response scenarios for each graphic conversion endpoint:
  maintain per-endpoint test modules (`test_convert_to_png.py`,
  `test_convert_to_bmp.py`, etc.) covering success, parameter customization,
  validation errors, multi-file guards, and async flows. Keep shared payload
  validation (output prefix and page-range cases) in a dedicated suite (e.g.,
  `tests/test_graphic_payload_validation.py`) that exercises every payload
  model.
- When introducing additional pdfRest endpoints, follow the same pattern used
  for graphic conversions: encapsulate shared request validation in a typed
  payload model, expose fully named client methods, and create a dedicated test
  module per endpoint that verifies success paths, request customization,
  validation errors, and async behavior. Centralize any reusable validation
  checks (e.g., common field requirements, payload serialization) in shared
  helper tests so new services inherit consistent coverage with minimal
  duplication.
- Prefer `pytest.mark.parametrize` (with `pytest.param(..., id="...")`) over
  explicit loops inside tests; nest parametrization for multi-dimensional
  coverage so each case appears as an individual test item.
- Live tests should verify that literal enumerations match pdfRest’s accepted
  values. Exercise format-specific options (e.g., each image format’s
  `color_model`) individually, and run smoothing enumerations through every
  enabled endpoint to confirm consistent server behaviour. Include “wildly”
  invalid values (e.g., bogus literals or mixed lists) alongside boundary
  failures so the server-side error messaging is exercised.
- Provide live integration tests under `tests/live/` (with an `__init__.py` so
  pytest discovers the package) that introspect payload models to enumerate
  valid/invalid literal values and numeric boundaries. These tests should vary a
  single parameter per request, assert success for legal inputs, and confirm
  pdfRest raises errors for out-of-range or unsupported values. When bypassing
  local validation to reach the server (e.g., for negative tests), inject the
  override via `extra_body` and expect `PdfRestApiError` (or the precise
  exception surfaced by the client).

## Commit & Pull Request Guidelines

- Follow the `area: summary` convention seen in `pdfassistant-chatbot` (e.g.,
  `client: Add document merge service`).
- Keep commit messages imperative and focused; squash fixups before opening a
  PR.
- Reference related issues or tickets in the PR description, and highlight
  breaking changes.
- Confirm CI passes (`pre-commit`, Python matrix) and note any manual
  verification or screenshots for behaviour updates.

## CI & Publishing Notes

- GitHub Actions run two workflows: `pre-commit` (no AWS credentials) and
  `Test and Publish` (Python 3.10–3.14 matrix).
- Only the release job assumes the AWS OIDC role to `uv build` and publish with
  `uv publish`.
- Keep CodeArtifact credentials out of source control; day-to-day development
  should rely solely on public dependencies.
