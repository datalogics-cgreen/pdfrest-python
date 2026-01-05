# /// script
# requires-python = "==3.10"
# dependencies = ["pdfrest", "exceptiongroup", "python-dotenv"]
# ///
"""Delete files with pdfRest's async client on Python 3.10.

Python 3.10 lacks the built-in `except*` syntax, so this example uses the
`exceptiongroup` backport to catch `PdfRestErrorGroup` and inspect individual
`PdfRestDeleteError` instances when cleanup fails.

Run with `uv run --project ../.. python delete_example.py`; the shared
`examples/resources/report.pdf` sample ships with the repository.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from dotenv import load_dotenv
from exceptiongroup import BaseExceptionGroup, catch

from pdfrest import AsyncPdfRestClient, PdfRestDeleteError

RESOURCE = Path(__file__).resolve().parents[2] / "resources" / "report.pdf"


def _log_delete_errors(group: BaseExceptionGroup) -> None:
    for error in group.exceptions:
        print(f"- Cleanup failed for {error.file_id}: {error.detail}")


async def delete_with_exceptiongroup_catch() -> None:
    load_dotenv()
    async with AsyncPdfRestClient() as client:
        uploaded = (await client.files.create_from_paths([RESOURCE]))[0]
        print(f"Uploaded {uploaded.name} with id={uploaded.id}")

        await client.files.delete(uploaded)
        print("First deletion succeeded.\n")

        print("Attempting to delete the same file again to trigger errors...")
        with catch({PdfRestDeleteError: _log_delete_errors}):
            await client.files.delete(uploaded)


if __name__ == "__main__":  # pragma: no cover - manual example
    asyncio.run(delete_with_exceptiongroup_catch())
