# Contributing

Thanks for contributing to `pdfrest`.

## Development setup

1. Install project tooling:

```bash
uv sync --group dev
```

2. (Recommended) install git hooks:

```bash
uv run pre-commit install
```

3. Verify package import/version:

```bash
uv run python -c "import pdfrest; print(pdfrest.__version__)"
```

## Code quality checks

Run these before opening a PR:

```bash
uv run ruff format .
uv run ruff check .
uv run basedpyright
```

## Tests

Quick local run:

```bash
uv run pytest -n auto --maxschedchunk 2
```

Full interpreter matrix with coverage artifacts (`coverage/py<version>/`):

```bash
uvx nox -s tests
```

Class/function coverage gate for client classes:

```bash
uvx nox -s class-coverage
```

To reuse existing coverage JSON without rerunning tests:

```bash
uvx nox -s class-coverage -- --no-tests
```

## Examples

Run all examples:

```bash
uvx nox -s examples
```

Run one example:

```bash
uv run nox -s run-example -- examples/delete/delete_example.py
```

## Docs preview (optional)

```bash
uv run mkdocs serve
uv run mkdocs build --strict
```
