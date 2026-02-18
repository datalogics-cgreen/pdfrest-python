from __future__ import annotations

from pdfrest.models import PdfRestFile


def make_source_file(file_id: str, mime_type: str, name: str) -> PdfRestFile:
    return PdfRestFile.model_validate(
        {
            "id": file_id,
            "name": name,
            "url": f"https://api.pdfrest.com/resource/{file_id}",
            "type": mime_type,
            "size": 512,
            "modified": "2024-01-01T00:00:00Z",
            "scheduledDeletionTimeUtc": None,
        }
    )
