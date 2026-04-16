"""Docling wrapper for PDF -> markdown conversion.

Docling is imported lazily inside ``parse_pdf`` so torch/easyocr (~2 GB
of deps) only load when a PDF actually needs parsing. The rest of the app
and its tests can import this module freely without paying the cold-start
cost. Install the optional extra with ``pip install -e ".[documents]"``
to enable real parsing; tests mock this function at the module level.
"""
from dataclasses import dataclass


@dataclass
class ParseResult:
    markdown: str
    page_count: int | None = None


def parse_pdf(file_path: str) -> ParseResult:
    """Parse a PDF into structured markdown using Docling.

    Docling is imported lazily so the rest of the app (and its tests) don't
    pay the torch/easyocr startup cost unless a PDF actually needs parsing.
    """
    from docling.document_converter import DocumentConverter

    converter = DocumentConverter()
    result = converter.convert(file_path)
    doc = result.document
    markdown = doc.export_to_markdown()

    page_count: int | None = None
    pages = getattr(doc, "pages", None)
    if pages is not None:
        try:
            page_count = len(pages)
        except TypeError:
            page_count = None

    return ParseResult(markdown=markdown, page_count=page_count)
