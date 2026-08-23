"""Text-first document parsers. PDFs need OCR when pages have insufficient text."""

from __future__ import annotations

from dataclasses import dataclass
from importlib.metadata import version
from pathlib import Path

from docx import Document
from pypdf import PdfReader


@dataclass(frozen=True, slots=True)
class ExtractedBlock:
    ordinal: int
    text: str
    locator: str
    page: int | None = None
    paragraph: int | None = None
    character_start: int | None = None
    character_end: int | None = None


@dataclass(frozen=True, slots=True)
class ExtractedDocument:
    blocks: tuple[ExtractedBlock, ...]
    parser_name: str
    parser_version: str
    needs_ocr: bool = False


def extract_document(path: str | Path, media_type: str) -> ExtractedDocument:
    path = Path(path)
    if media_type == "text/plain":
        return _txt(path)
    if media_type.endswith("wordprocessingml.document"):
        return _docx(path)
    if media_type == "application/pdf":
        return _pdf(path)
    raise ValueError("Unsupported document media type")


def parser_metadata(media_type: str) -> tuple[str, str]:
    """Return the parser identity before extraction so failed runs stay auditable."""
    if media_type == "text/plain":
        return "utf-8", "builtin"
    if media_type.endswith("wordprocessingml.document"):
        return "python-docx", version("python-docx")
    if media_type == "application/pdf":
        return "pypdf", version("pypdf")
    return "validation", "builtin"


def _txt(path: Path) -> ExtractedDocument:
    text = path.read_text(encoding="utf-8-sig")
    return ExtractedDocument((ExtractedBlock(0, text, f"characters:0-{len(text)}", character_start=0, character_end=len(text)),) if text else (), "utf-8", "builtin")


def _docx(path: Path) -> ExtractedDocument:
    blocks = tuple(
        ExtractedBlock(ordinal, paragraph.text.strip(), f"paragraph:{paragraph_index}", paragraph=paragraph_index)
        for ordinal, (paragraph_index, paragraph) in enumerate(
            (item for item in enumerate(Document(path).paragraphs, start=1) if item[1].text.strip())
        )
    )
    return ExtractedDocument(blocks, "python-docx", version("python-docx"))


def _pdf(path: Path) -> ExtractedDocument:
    reader = PdfReader(path)
    blocks = tuple(
        ExtractedBlock(index - 1, text, f"page:{index}", page=index)
        for index, page in enumerate(reader.pages, start=1)
        if (text := (page.extract_text() or "").strip())
    )
    # Native PDFs require at least one nontrivial page of selectable text; otherwise OCR is honest.
    needs_ocr = not blocks or sum(len(block.text) for block in blocks) < 20
    return ExtractedDocument(blocks, "pypdf", version("pypdf"), needs_ocr)
