# Getting started

This guide walks through a Cloud-first setup for `pdfrest` (the Python package
published on PyPI) so you can make your first API call quickly.

## Before you begin

- A Python runtime (3.10+ recommended for this SDK).
- A local PDF file to test with.
- A pdfRest Cloud account and API key.

For the official Cloud onboarding flow, see:

- [pdfRest API Toolkit Cloud: Getting Started](https://docs.pdfrest.com/pdfrest-api-toolkit-cloud/getting-started/)
- [Python API reference](api-reference.md)
- [API Lab](https://pdfrest.com/apilab/)

## 1. Create a project and install `pdfrest`

### Recommended: uv

=== "uv (Recommended)"
    ```bash
    mkdir pdfrest-quickstart
    cd pdfrest-quickstart
    uv init
    uv add pdfrest
    ```

=== "pip + venv"
    ```bash
    mkdir pdfrest-quickstart
    cd pdfrest-quickstart
    python -m venv .venv
    source .venv/bin/activate
    pip install pdfrest
    ```

=== "Poetry"
    ```bash
    mkdir pdfrest-quickstart
    cd pdfrest-quickstart
    poetry init --no-interaction
    poetry add pdfrest
    ```

## 2. Get your pdfRest Cloud API key

1. Create or sign in to your account at [pdfRest.com](https://pdfrest.com/).
2. Follow the Cloud onboarding steps in
   [Getting Started](https://docs.pdfrest.com/pdfrest-api-toolkit-cloud/getting-started/).
3. Copy your API key and export it as `PDFREST_API_KEY` in your shell.

=== "macOS / Linux (bash/zsh)"
    ```bash
    export PDFREST_API_KEY="your-api-key-here"
    ```

=== "Windows PowerShell"
    ```powershell
    $env:PDFREST_API_KEY="your-api-key-here"
    ```

!!! tip
    The [API Lab](https://pdfrest.com/apilab/) is useful for testing endpoints
    interactively and generating starter code samples before integrating them
    into your project.

### Demo keys and redacted values

If you are using a demo/free-tier key, some API responses may include redacted
values (for example `fa***`, `tr**`, masked strings, or placeholder IDs).

To keep response models parseable, the SDK replaces certain known demo-redacted
values in a few response fields:

- `PdfRestInfoResponse` boolean fields:
  `tagged`, `image_only`, `contains_annotations`, `contains_signature`,
  `restrict_permissions_set`, `contains_xfa`, `contains_acroforms`,
  `contains_javascript`, `contains_transparency`, `contains_embedded_file`,
  `uses_embedded_fonts`, `uses_nonembedded_fonts`, `pdfa`, `pdfua_claim`,
  `pdfe_claim`, `pdfx_claim`, `requires_password_to_open`
- `PdfRestInfoResponse.file_size` -> replaced with `0` when redacted
- `PdfRestInfoResponse.all_queries_processed` -> replaced with `True` when redacted
- unzip response file IDs are sanitized before file-info lookup, so
  `PdfRestFileBasedResponse.output_file.id` may be the null UUID
  `00000000-0000-4000-8000-000000000000` when demo IDs are redacted

When a replacement happens, the SDK logs a warning in this format:

`Demo value <val> detected in <field-name>; replaced with <replacement>`

To see these warnings in your app, configure Python logging (example):

```python
import logging

logging.basicConfig(level=logging.WARNING)
logging.getLogger("pdfrest.models").setLevel(logging.WARNING)
```

## 3. Add a short example program

Create `quickstart.py`:

```python
from pathlib import Path

from pdfrest import PdfRestClient

input_pdf = Path("input.pdf")

if not input_pdf.exists():
    raise FileNotFoundError(
        "Place a test PDF at ./input.pdf before running this script."
    )

with PdfRestClient() as client:
    uploaded = client.files.create_from_paths([input_pdf])[0]
    document = client.extract_pdf_text(uploaded, full_text="document")

full_text = ""
if document.full_text is not None and document.full_text.document_text is not None:
    full_text = document.full_text.document_text

print(f"Input file id: {uploaded.id}")
print("Extracted text preview:")
print(full_text[:500] if full_text else "(no text returned)")
```

What this script does:

- Uploads `input.pdf` to pdfRest Cloud.
- Calls `extract_pdf_text`.
- Prints a short text preview from the response.

## 4. Run the example

=== "uv"
    ```bash
    uv run python quickstart.py
    ```

=== "pip + venv"
    ```bash
    python quickstart.py
    ```

=== "Poetry"
    ```bash
    poetry run python quickstart.py
    ```

## 5. Next steps

- Browse endpoint options in the
  [Python API reference](api-reference.md).
- Explore additional endpoint behavior and payload examples in
  [API Lab](https://pdfrest.com/apilab/).
