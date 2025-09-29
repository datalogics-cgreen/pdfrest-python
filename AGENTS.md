# Repository Guidelines

## Project Structure & Module Organization

- Source lives in `src/pdfrest/`; expose public APIs via `__all__` and keep
  package metadata in `pyproject.toml`.
- Tests sit in `tests/` mirroring the module layout (e.g.,
  `tests/test_client.py`).
- Workflow definitions are in `.github/workflows/`; adjust only when CI
  requirements change.
- Documentation and contributor notes reside at the repo root (`README.md`,
  `AGENTS.md`).

## Build, Test, and Development Commands

- `uv sync --group dev` — create/update the virtual environment with lint,
  type-check, and test tooling.
- `uv run pre-commit run --all-files` — enforce formatting and lint rules before
  pushing.
- `uv run pytest` — execute the suite with the active interpreter.
- `uv build` — produce wheels and sdists identical to the release workflow.

## Coding Style & Naming Conventions

- Target Python 3.9–3.13; use 4-space indentation and type hints for public
  APIs.
- Black + isort (via ruff) enforce formatting; run through pre-commit prior to
  review.
- Use `snake_case` for functions/modules, `PascalCase` for classes, and
  `UPPER_SNAKE_CASE` for constants.
- Prefer `pathlib`, f-strings, and other modern stdlib features—pyupgrade rules
  will flag legacy code.

## Testing Guidelines

- Write pytest tests: files named `test_*.py`, test functions `test_*`, fixtures
  in `conftest.py` where shared.
- Ensure high-value coverage of public functions and edge cases; document intent
  in test docstrings when non-obvious.
- For interpreter compatibility, execute the matrix locally:
  ```bash
  for py in 3.9 3.10 3.11 3.12 3.13; do
    UV_PROJECT_ENVIRONMENT=.venv-$py uv sync --group dev --python $py
    UV_PROJECT_ENVIRONMENT=.venv-$py uv run --python $py pytest
  done
  ```

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
  `Test and Publish` (Python 3.9–3.13 matrix).
- Only the release job assumes the AWS OIDC role to `uv build` and publish with
  `uv tool run --from twine twine upload`.
- Keep CodeArtifact credentials out of source control; day-to-day development
  should rely solely on public dependencies.
