from __future__ import annotations

import ast
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import pytest

from matter_context.ingestion.parsers import extract_document
from matter_context.ingestion.validation import DocumentValidationError, MAX_UPLOAD_BYTES, validate_document, validate_filename, validate_storable_path
from matter_context.application.ingestion import DocumentIngestionService
from matter_context.application.cases import PersistedMatterWorkspaceService
from matter_context.application.matters import MatterService
from matter_context.storage.attachments import AttachmentStore
from matter_context.storage.database import Database, upgrade_database
from matter_context.storage.unit_of_work import SqlAlchemyUnitOfWork


def test_application_domain_and_execution_do_not_import_storage() -> None:
    source_root = Path(__file__).parents[1] / "src" / "matter_context"
    for package in ("application", "domain", "execution"):
        for path in (source_root / package).rglob("*.py"):
            tree = ast.parse(path.read_text(), filename=str(path))
            imported_modules = (
                node.module if isinstance(node, ast.ImportFrom) else alias.name
                for node in ast.walk(tree)
                if isinstance(node, (ast.Import, ast.ImportFrom))
                for alias in (node.names if isinstance(node, ast.Import) else (node,))
            )
            assert all(
                module is None or not module.startswith("matter_context.storage")
                for module in imported_modules
            ), f"{path.relative_to(source_root)} imports matter_context.storage"


def _write_native_pdf(path: Path, page_texts: list[str]) -> None:
    """Create a minimal selectable-text PDF without adding a production dependency."""
    objects: dict[int, bytes] = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        3: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    }
    page_numbers = []
    for index, page_text in enumerate(page_texts):
        page_number = 4 + index * 2
        content_number = page_number + 1
        escaped = page_text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)").encode()
        stream = b"BT /F1 12 Tf 72 720 Td (" + escaped + b") Tj ET"
        objects[content_number] = b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream"
        objects[page_number] = b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 3 0 R >> >> /Contents " + str(content_number).encode() + b" 0 R >>"
        page_numbers.append(page_number)
    objects[2] = b"<< /Type /Pages /Kids [" + b" ".join(f"{number} 0 R".encode() for number in page_numbers) + b"] /Count " + str(len(page_numbers)).encode() + b" >>"
    payload = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number in range(1, max(objects) + 1):
        offsets.append(len(payload))
        payload.extend(f"{number} 0 obj\n".encode() + objects[number] + b"\nendobj\n")
    startxref = len(payload)
    payload.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode())
    payload.extend(b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets[1:]))
    payload.extend(f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{startxref}\n%%EOF\n".encode())
    path.write_bytes(payload)


def _write_bilingual_native_pdf(path: Path) -> None:
    def stream(content: bytes) -> bytes:
        return b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream"

    cmap = b"""/CIDInit /ProcSet findresource begin
12 dict begin
begincmap
/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def
/CMapName /Adobe-Identity-UCS def
/CMapType 2 def
1 begincodespacerange
<0000> <FFFF>
endcodespacerange
4 beginbfchar
<4E2D> <4E2D>
<6587> <6587>
<8BC1> <8BC1>
<636E> <636E>
endbfchar
endcmap
CMapName currentdict /CMap defineresource pop
end
end"""
    objects = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: b"<< /Type /Pages /Kids [4 0 R 6 0 R] /Count 2 >>",
        3: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        4: b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 3 0 R >> >> /Contents 5 0 R >>",
        5: stream(b"BT /F1 12 Tf 72 720 Td (English native PDF evidence.) Tj ET"),
        6: b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F2 8 0 R >> >> /Contents 9 0 R >>",
        7: b"<< /Type /FontDescriptor /FontName /Adobe-Identity-UCS /Flags 4 /Ascent 880 /Descent -120 /CapHeight 700 /ItalicAngle 0 /StemV 80 >>",
        8: b"<< /Type /Font /Subtype /Type0 /BaseFont /Adobe-Identity-UCS /Encoding /Identity-H /DescendantFonts [10 0 R] /ToUnicode 11 0 R >>",
        9: stream(b"BT /F2 12 Tf 72 720 Td <4E2D65878BC1636E> Tj ET"),
        10: b"<< /Type /Font /Subtype /CIDFontType2 /BaseFont /Adobe-Identity-UCS /CIDSystemInfo << /Registry (Adobe) /Ordering (Identity) /Supplement 0 >> /FontDescriptor 7 0 R /DW 1000 >>",
        11: stream(cmap),
    }
    payload = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number in range(1, 12):
        offsets.append(len(payload))
        payload.extend(f"{number} 0 obj\n".encode() + objects[number] + b"\nendobj\n")
    startxref = len(payload)
    payload.extend(b"xref\n0 12\n0000000000 65535 f \n")
    payload.extend(b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets[1:]))
    payload.extend(f"trailer\n<< /Size 12 /Root 1 0 R >>\nstartxref\n{startxref}\n%%EOF\n".encode())
    path.write_bytes(payload)


def test_utf8_txt_preserves_chinese_and_character_locator(tmp_path: Path) -> None:
    document = tmp_path / "当事人说明.txt"
    document.write_text("中文证据\nEnglish evidence", encoding="utf-8")

    result = extract_document(document, "text/plain")

    assert [(block.ordinal, block.text, block.character_start, block.character_end) for block in result.blocks] == [
        (0, "中文证据\nEnglish evidence", 0, len("中文证据\nEnglish evidence")),
    ]
    assert result.parser_name == "utf-8"


def test_docx_extracts_nonempty_one_based_paragraphs(tmp_path: Path) -> None:
    docx = pytest.importorskip("docx")
    document = docx.Document()
    document.add_paragraph("First paragraph")
    document.add_paragraph("   ")
    document.add_paragraph("第二段")
    path = tmp_path / "evidence.docx"
    document.save(path)

    result = extract_document(path, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")

    assert [(block.ordinal, block.paragraph, block.text) for block in result.blocks] == [
        (0, 1, "First paragraph"), (1, 3, "第二段"),
    ]


def test_persisted_docx_retains_one_based_paragraph_blocks(tmp_path: Path) -> None:
    docx = pytest.importorskip("docx")
    document = docx.Document()
    document.add_paragraph("English paragraph")
    document.add_paragraph("中文段落")
    path = tmp_path / "证据.docx"
    document.save(path)
    database = Database.from_url(f"sqlite:///{tmp_path / 'docx.sqlite3'}")
    upgrade_database(str(database.engine.url))
    factory = lambda: SqlAlchemyUnitOfWork(database.session_factory)
    matter = MatterService(factory).create_matter("DOCX")

    result = DocumentIngestionService(factory, AttachmentStore(tmp_path / "attachments")).ingest(matter.identifier, path)
    with factory() as uow:
        blocks = uow.content_blocks.list_for_source(result.source_id)
        source = uow.sources.get(result.source_id)

    assert result.status.value == "ready"
    assert source and source.original_filename == "证据.docx"
    assert [(block.ordinal, block.paragraph, block.text) for block in blocks] == [
        (0, 1, "English paragraph"), (1, 2, "中文段落"),
    ]


def test_scan_only_pdf_is_honestly_marked_needs_ocr(tmp_path: Path) -> None:
    pypdf = pytest.importorskip("pypdf")
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=100, height=100)
    path = tmp_path / "scan.pdf"
    with path.open("wb") as output:
        writer.write(output)

    result = extract_document(path, "application/pdf")

    assert result.blocks == ()
    assert result.needs_ocr


def test_native_pdf_persists_ordered_one_based_page_blocks(tmp_path: Path) -> None:
    database = Database.from_url(f"sqlite:///{tmp_path / 'native-pdf.sqlite3'}")
    upgrade_database(str(database.engine.url))
    factory = lambda: SqlAlchemyUnitOfWork(database.session_factory)
    matter = MatterService(factory).create_matter("Native PDF")
    path = tmp_path / "native.pdf"
    _write_bilingual_native_pdf(path)

    result = DocumentIngestionService(factory, AttachmentStore(tmp_path / "attachments")).ingest(matter.identifier, path)
    with factory() as uow:
        blocks = uow.content_blocks.list_for_source(result.source_id)

    assert result.status.value == "ready"
    assert [(block.ordinal, block.page, block.text) for block in blocks] == [
        (0, 1, "English native PDF evidence."), (1, 2, "中文证据"),
    ]


def test_scan_only_pdf_persists_needs_ocr_status(tmp_path: Path) -> None:
    pypdf = pytest.importorskip("pypdf")
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=100, height=100)
    path = tmp_path / "scan-only.pdf"
    with path.open("wb") as output:
        writer.write(output)
    database = Database.from_url(f"sqlite:///{tmp_path / 'scan.sqlite3'}")
    upgrade_database(str(database.engine.url))
    factory = lambda: SqlAlchemyUnitOfWork(database.session_factory)
    matter = MatterService(factory).create_matter("Scan only")

    result = DocumentIngestionService(factory, AttachmentStore(tmp_path / "attachments")).ingest(matter.identifier, path)
    with factory() as uow:
        source = uow.sources.get(result.source_id)
        run = uow.processing_runs.get(result.run_id)

    assert result.status.value == "needs_ocr"
    assert source and str(source.ingestion_status) == "needs_ocr" and str(source.extraction_status) == "needs_ocr"
    assert run and run.status.value == "partial" and run.parser_name == "pypdf"


def test_validation_rejects_traversal_binary_spoof_and_oversize(tmp_path: Path) -> None:
    binary = tmp_path / "binary.txt"
    binary.write_bytes(b"text\x00payload")
    late_binary = tmp_path / "late-binary.txt"
    late_binary.write_bytes(b"a" * 8192 + b"\x00\xff")
    spoof = tmp_path / "spoof.pdf"
    spoof.write_bytes(b"not a PDF")
    oversized = tmp_path / "large.txt"
    oversized.write_bytes(b"a" * (MAX_UPLOAD_BYTES + 1))

    for path in (binary, late_binary, spoof, oversized):
        with pytest.raises(DocumentValidationError):
            validate_document(path)
    with pytest.raises(DocumentValidationError):
        validate_filename("../escape.pdf")
    traversal = tmp_path / "nested" / ".." / "escape.txt"
    traversal.parent.parent.mkdir(exist_ok=True)
    (tmp_path / "escape.txt").write_text("safe bytes", encoding="utf-8")
    with pytest.raises(DocumentValidationError):
        validate_storable_path(traversal)
    assert validate_filename("证据.pdf") == "证据.pdf"


def test_document_ingestion_preserves_duplicate_originals_and_failed_records(tmp_path: Path) -> None:
    database = Database.from_url(f"sqlite:///{tmp_path / 'ingestion.sqlite3'}")
    upgrade_database(str(database.engine.url))
    factory = lambda: SqlAlchemyUnitOfWork(database.session_factory)
    matter = MatterService(factory).create_matter("Document matter")
    service = DocumentIngestionService(factory, AttachmentStore(tmp_path / "attachments"))
    text = tmp_path / "证据.txt"
    text.write_text("证据内容", encoding="utf-8")

    first = service.ingest(matter.identifier, text)
    duplicate = service.ingest(matter.identifier, text)
    corrupt = tmp_path / "corrupt.pdf"
    corrupt.write_bytes(b"%PDF-1.7 broken")
    failed = service.ingest(matter.identifier, corrupt)
    unsupported = tmp_path / "unsupported.rtf"
    unsupported.write_text("unparseable format", encoding="utf-8")
    unsupported_result = service.ingest(matter.identifier, unsupported)

    with factory() as uow:
        first_blocks = uow.content_blocks.list_for_source(first.source_id)
        duplicate_source = uow.sources.get(duplicate.source_id)
        failed_source = uow.sources.get(failed.source_id)
        failed_run = uow.processing_runs.get(failed.run_id)
        unsupported_source = uow.sources.get(unsupported_result.source_id)
        unsupported_run = uow.processing_runs.get(unsupported_result.run_id)
    assert first.status.value == "ready"
    assert first_blocks[0].text == "证据内容"
    assert duplicate.duplicate_of_id == first.source_id
    assert duplicate_source and duplicate_source.attachment_path
    assert failed.status.value == "failed"
    assert failed_source and failed_source.attachment_path and str(failed_source.ingestion_status) == "failed"
    assert failed_run and failed_run.error_summary and failed_run.parser_name == "pypdf" and failed_run.parser_version
    assert str(tmp_path) not in failed_run.error_summary
    assert unsupported_result.status.value == "failed"
    assert unsupported_source and unsupported_source.attachment_path
    assert unsupported_run and unsupported_run.parser_name == "validation" and unsupported_run.parser_version == "builtin"


def test_concurrent_same_matter_imports_link_every_later_attempt_to_one_canonical_source(tmp_path: Path) -> None:
    database = Database.from_url(f"sqlite:///{tmp_path / 'concurrent.sqlite3'}")
    upgrade_database(str(database.engine.url))
    factory = lambda: SqlAlchemyUnitOfWork(database.session_factory)
    matter = MatterService(factory).create_matter("Concurrent duplicates")
    document = tmp_path / "same.txt"
    document.write_text("same payload", encoding="utf-8")
    attachments = AttachmentStore(tmp_path / "attachments")

    def ingest_once():
        return DocumentIngestionService(factory, attachments).ingest(matter.identifier, document)

    with ThreadPoolExecutor(max_workers=3) as executor:
        results = list(executor.map(lambda _: ingest_once(), range(3)))
    with factory() as uow:
        sources = [uow.sources.get(result.source_id) for result in results]

    canonical = [source for source in sources if source and source.duplicate_of_id is None]
    assert len(canonical) == 1
    assert {source.duplicate_of_id for source in sources if source and source.duplicate_of_id} == {canonical[0].identifier}


def test_registration_failure_removes_unreferenced_managed_original(tmp_path: Path) -> None:
    database = Database.from_url(f"sqlite:///{tmp_path / 'orphan.sqlite3'}")
    upgrade_database(str(database.engine.url))
    factory = lambda: SqlAlchemyUnitOfWork(database.session_factory)
    attachments = tmp_path / "attachments"
    service = DocumentIngestionService(factory, AttachmentStore(attachments))
    document = tmp_path / "evidence.txt"
    document.write_text("evidence", encoding="utf-8")

    with pytest.raises(Exception):
        service.ingest("missing-matter", document)

    assert not list(attachments.rglob("*"))


def test_workspace_exposes_only_resolved_managed_original_path(tmp_path: Path) -> None:
    database = Database.from_url(f"sqlite:///{tmp_path / 'workspace.sqlite3'}")
    upgrade_database(str(database.engine.url))
    factory = lambda: SqlAlchemyUnitOfWork(database.session_factory)
    attachments = AttachmentStore(tmp_path / "attachments")
    workspace = PersistedMatterWorkspaceService(factory, attachments)
    matter = workspace.create_matter("Workspace matter")
    document = tmp_path / "evidence.txt"
    document.write_text("managed original", encoding="utf-8")

    result = workspace.ingest_document(matter.identifier, str(document))
    source = workspace.list_sources(matter.identifier)[0]

    assert result.status.value == "ready"
    assert source.original_path is not None
    assert Path(source.original_path).is_relative_to(attachments.root)
