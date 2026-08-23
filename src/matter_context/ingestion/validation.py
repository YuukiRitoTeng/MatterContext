"""Input checks for local document imports (maximum payload: 50 MiB)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

MAX_UPLOAD_BYTES = 50 * 1024 * 1024
_MEDIA_TYPES = {".txt": "text/plain", ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".pdf": "application/pdf"}


class DocumentValidationError(ValueError):
    """A user-safe reason an import cannot start."""


@dataclass(frozen=True, slots=True)
class ValidatedDocument:
    path: Path
    filename: str
    media_type: str


def validate_document(path: str | Path, *, filename: str | None = None) -> ValidatedDocument:
    candidate = Path(path)
    if ".." in candidate.parts:
        raise DocumentValidationError("Document path must not traverse directories")
    display_filename = validate_filename(filename or candidate.name)
    if not candidate.is_file():
        raise DocumentValidationError("Document does not exist or is not a regular file")
    suffix = Path(display_filename).suffix.lower()
    media_type = _MEDIA_TYPES.get(suffix)
    if media_type is None:
        raise DocumentValidationError("Only TXT, DOCX, and PDF files are supported")
    if candidate.stat().st_size > MAX_UPLOAD_BYTES:
        raise DocumentValidationError("Document exceeds the 50 MiB limit")
    with candidate.open("rb") as source:
        signature = source.read(8)
    if suffix == ".pdf" and not signature.startswith(b"%PDF-"):
        raise DocumentValidationError("PDF signature is invalid")
    if suffix == ".docx" and not signature.startswith(b"PK\x03\x04"):
        raise DocumentValidationError("DOCX signature is invalid")
    if suffix == ".txt" and _is_binary_text(candidate):
        raise DocumentValidationError("TXT file appears to be binary")
    return ValidatedDocument(candidate, display_filename, media_type)


def validate_storable_path(path: str | Path) -> Path:
    """Check path and size constraints before copying an original for failed-run audit."""
    candidate = Path(path)
    if ".." in candidate.parts:
        raise DocumentValidationError("Document path must not traverse directories")
    validate_filename(candidate.name)
    if not candidate.is_file():
        raise DocumentValidationError("Document does not exist or is not a regular file")
    if candidate.stat().st_size > MAX_UPLOAD_BYTES:
        raise DocumentValidationError("Document exceeds the 50 MiB limit")
    return candidate


def media_type_for_filename(filename: str) -> str:
    """Use a neutral type for rejected formats while preserving their original."""
    return _MEDIA_TYPES.get(Path(validate_filename(filename)).suffix.lower(), "application/octet-stream")


def validate_filename(filename: str) -> str:
    """Validate a display filename independently of the caller's filesystem path."""
    if not filename or Path(filename).name != filename or "\\" in filename or filename in {".", ".."}:
        raise DocumentValidationError("Document filename must not contain a path")
    return filename


def _is_binary_text(path: Path) -> bool:
    total = controls = 0
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            if b"\x00" in chunk:
                return True
            total += len(chunk)
            controls += sum(byte < 32 and byte not in {9, 10, 12, 13} for byte in chunk)
    return total > 0 and controls / total > 0.05
