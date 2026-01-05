# /// script
# requires-python = ">=3.11"
# dependencies = ["pdfrest", "python-dotenv"]
# ///
"""Delete files with pdfRest's async client on Python 3.11+.

This sample shows how to:

1. Upload a local resource so we have a file id to delete.
2. Delete that file successfully.
3. Demonstrate how `PdfRestErrorGroup` behaves when we try to delete the same
   file again (Python 3.11 also allows `except* PdfRestDeleteError` if you want
   to tighten the example even further).

Run with `uv run --project ../.. python delete_example.py`; the script uses the
checked-in `examples/resources/report.pdf` sample so no additional setup is
required.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from dotenv import load_dotenv

from pdfrest import AsyncPdfRestClient, PdfRestDeleteError

RESOURCE = Path(__file__).resolve().parents[1] / "resources" / "report.pdf"


async def delete_with_except_star() -> None:
    load_dotenv()
    async with AsyncPdfRestClient() as client:
        uploaded = (await client.files.create_from_paths([RESOURCE]))[0]
        print(f"Uploaded {uploaded.name} with id={uploaded.id}")

        await client.files.delete(uploaded)
        print("First deletion succeeded.\n")

        print("Attempting to delete the same file again to trigger errors...")
        try:
            await client.files.delete(uploaded)
        except* PdfRestDeleteError as group:
            for error in group.exceptions:
                print(f"- Cleanup failed for {error.file_id}: {error.detail}")
        else:  # pragma: no cover - would require server bug
            print("Second deletion unexpectedly succeeded.")


if __name__ == "__main__":  # pragma: no cover - manual example
    asyncio.run(delete_with_except_star())
