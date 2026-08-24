"""Text-first document parsers. PDFs need OCR when pages have insufficient text."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
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


class ExtractionCompleteness(StrEnum):
    """Whether this adapter can stand behind the extracted content as complete."""

    COMPLETE = "complete"
    PARTIAL = "partial"
    NO_TEXT = "no_text"


@dataclass(frozen=True, slots=True)
class ExtractedDocument:
    blocks: tuple[ExtractedBlock, ...]
    parser_name: str
    parser_version: str
    completeness: ExtractionCompleteness = ExtractionCompleteness.COMPLETE


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
    blocks = (ExtractedBlock(0, text, f"characters:0-{len(text)}", character_start=0, character_end=len(text)),) if text else ()
    completeness = ExtractionCompleteness.COMPLETE if blocks else ExtractionCompleteness.NO_TEXT
    return ExtractedDocument(blocks, "utf-8", "builtin", completeness)


def _docx(path: Path) -> ExtractedDocument:
    document = Document(path)
    blocks = tuple(
        ExtractedBlock(ordinal, paragraph.text.strip(), f"paragraph:{paragraph_index}", paragraph=paragraph_index)
        for ordinal, (paragraph_index, paragraph) in enumerate(
            (item for item in enumerate(document.paragraphs, start=1) if item[1].text.strip())
        )
    )
    # python-docx exposes tables separately. Until a table adapter exists, their
    # presence means paragraph extraction is not a complete representation.
    if document.tables:
        completeness = ExtractionCompleteness.PARTIAL
    elif blocks:
        completeness = ExtractionCompleteness.COMPLETE
    else:
        completeness = ExtractionCompleteness.NO_TEXT
    return ExtractedDocument(blocks, "python-docx", version("python-docx"), completeness)


def _pdf(path: Path) -> ExtractedDocument:
    reader = PdfReader(path)
    page_text = tuple((page.extract_text() or "").strip() for page in reader.pages)
    blocks = tuple(
        ExtractedBlock(index - 1, text, f"page:{index}", page=index)
        for index, text in enumerate(page_text, start=1)
        if text
    )
    if not blocks:
        completeness = ExtractionCompleteness.NO_TEXT
    elif len(blocks) != len(page_text):
        completeness = ExtractionCompleteness.PARTIAL
    else:
        completeness = ExtractionCompleteness.COMPLETE
    return ExtractedDocument(blocks, "pypdf", version("pypdf"), completeness)
