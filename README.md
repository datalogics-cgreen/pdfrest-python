# pdfrest

Python client library for the PDFRest service. The project is managed with
[uv](https://docs.astral.sh/uv/) and targets Python 3.9 and newer.

## Running examples

```bash
uvx nox -s examples
uv run nox -s run-example -- examples/delete/delete_example.py
```

## Getting started

```bash
uv sync
uv run python -c "import pdfrest; print(pdfrest.__version__)"
```

## Development

To install the tooling used by CI locally, include the `--group dev` flag:

```bash
uv sync --group dev
```

It is recommended to enable the pre-commit hooks after installation:

```bash
uv run pre-commit install
```

Run the test suite with:

```bash
uv run pytest
```

Check per-function coverage for the client classes:

```bash
uvx nox -s class-coverage
```

To reuse an existing `coverage/py<version>/coverage.json` without rerunning
tests, add `-- --no-tests` (and optional `--coverage-json path`).
