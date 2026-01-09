# /// script
# requires-python = ">=3.10"
# dependencies = ["pdfrest", "python-dotenv", "rich"]
# ///
"""Render extracted words with coordinates and style metadata.

This sample demonstrates how to:

1. Upload the bundled ``examples/resources/report.pdf`` resource.
2. Request JSON output from :func:`PdfRestClient.extract_pdf_text` while turning on
   word-level coordinates and styling data.
3. Display the returned metadata as a Rich table.

Run with ``uv run --project ../.. python extract_pdf_text_example.py`` after
setting ``PDFREST_API_KEY`` (``python-dotenv`` will also load `.env` if present).
"""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

from pdfrest import PdfRestClient
from pdfrest.models import (
    ExtractedTextDocument,
    ExtractedTextPoint,
    ExtractedTextWord,
    ExtractedTextWordCoordinates,
)

RESOURCE = Path(__file__).resolve().parents[1] / "resources" / "report.pdf"


def _format_point(point: ExtractedTextPoint | None) -> str:
    if point is None:
        return "—"
    return f"({point.x:.2f}, {point.y:.2f})"


def _format_color(word: ExtractedTextWord) -> str:
    style = word.style
    if style is None or style.color is None:
        return "—"
    color = style.color
    values = ", ".join(str(value) for value in color.values)
    return f"{color.space}: {values}"


def _format_font(word: ExtractedTextWord) -> str:
    style = word.style
    if style is None:
        return "—"
    font = style.font
    return f"{font.name} ({font.size:.1f} pt)"


def _build_word_table(document: ExtractedTextDocument) -> Table:
    table = Table(title="Extracted Words with Coordinates and Style")
    table.add_column("Word", style="bold")
    table.add_column("Page", justify="right")
    table.add_column("Top Left")
    table.add_column("Top Right")
    table.add_column("Bottom Left")
    table.add_column("Bottom Right")
    table.add_column("Color")
    table.add_column("Font")

    for word in document.words or []:
        coords: ExtractedTextWordCoordinates | None = word.coordinates
        table.add_row(
            word.text,
            str(word.page),
            _format_point(coords.top_left if coords else None),
            _format_point(coords.top_right if coords else None),
            _format_point(coords.bottom_left if coords else None),
            _format_point(coords.bottom_right if coords else None),
            _format_color(word),
            _format_font(word),
        )
    return table


def list_words_with_coordinates() -> None:
    load_dotenv()
    console = Console()

    with PdfRestClient() as client:
        uploaded = client.files.create_from_paths([RESOURCE])[0]
        document = client.extract_pdf_text(
            uploaded,
            full_text="by_page",
            preserve_line_breaks=True,
            word_style=True,
            word_coordinates=True,
        )

    words = document.words or []
    console.print(f"Extracted {len(words)} words from [bold]{uploaded.name}[/bold].")
    if not words:
        console.print("[yellow]This document did not include word metadata.[/yellow]")
        return

    table = _build_word_table(document)
    console.print(table)


if __name__ == "__main__":  # pragma: no cover - manual example
    list_words_with_coordinates()
