"""Safe local attachment persistence beneath the configured attachment root."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path, PurePosixPath
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True)
class StoredAttachment:
    relative_path: str
    sha256: str
    size: int


class AttachmentStore:
    def __init__(self, root: Path) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def store(self, source: Path, *, max_bytes: int | None = None) -> StoredAttachment:
        source = Path(source)
        if not source.is_file():
            raise FileNotFoundError(source)
        identifier = str(uuid4())
        relative = PurePosixPath(identifier[:2]) / identifier
        target = self.resolve(relative.as_posix())
        target.parent.mkdir(parents=True, exist_ok=True)
        digest = sha256()
        size = 0
        try:
            with source.open("rb") as input_file, target.open("xb") as output_file:
                while chunk := input_file.read(1024 * 1024):
                    size += len(chunk)
                    if max_bytes is not None and size > max_bytes:
                        raise ValueError("Attachment exceeds size limit")
                    digest.update(chunk)
                    output_file.write(chunk)
        except Exception:
            target.unlink(missing_ok=True)
            raise
        return StoredAttachment(relative.as_posix(), digest.hexdigest(), size)

    def delete(self, relative_path: str) -> None:
        target = self.resolve(relative_path)
        target.unlink(missing_ok=True)
        try:
            target.parent.rmdir()
        except OSError:
            pass

    def resolve(self, relative_path: str) -> Path:
        relative = PurePosixPath(relative_path)
        if relative.is_absolute() or ".." in relative.parts or relative_path != relative.as_posix():
            raise ValueError("Attachment path must be a generated, normalized relative path")
        if len(relative.parts) != 2 or len(relative.parts[0]) != 2 or len(relative.parts[1]) != 36:
            raise ValueError("Attachment path must be a generated attachment identifier")
        try:
            generated = str(UUID(relative.parts[1]))
        except ValueError as error:
            raise ValueError("Attachment path must be a generated attachment identifier") from error
        if generated[:2] != relative.parts[0]:
            raise ValueError("Attachment path must be a generated attachment identifier")
        resolved = (self.root / Path(*relative.parts)).resolve()
        if resolved.parent != self.root and self.root not in resolved.parents:
            raise ValueError("Attachment path escapes attachment store")
        return resolved
