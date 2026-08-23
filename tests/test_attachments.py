from __future__ import annotations

from hashlib import sha256

import pytest

from matter_context.storage.attachments import AttachmentStore


def test_attachment_storage_hashes_payload_and_stays_contained(tmp_path) -> None:
    input_file = tmp_path / "client-name.pdf"
    input_file.write_bytes(b"evidence")
    store = AttachmentStore(tmp_path / "attachments")

    stored = store.store(input_file)

    assert stored.sha256 == sha256(b"evidence").hexdigest()
    assert store.resolve(stored.relative_path).read_bytes() == b"evidence"
    with pytest.raises(ValueError):
        store.resolve("../outside")
    with pytest.raises(ValueError):
        store.resolve("/absolute")
