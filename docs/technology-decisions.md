# Technology Decisions

## Decision status

These are confirmed Phase 1 implementation choices. They favor a dependable Windows desktop experience, direct integration with the Python business stack, local data control, and a short path that can still grow.

## Application stack

Document input is bounded at 50 MiB and path-checked before copying. The original is then preserved and registered before extension plus TXT/PDF/DOCX signature validation and extraction, so rejected formats remain auditable. `python-docx` extracts nonempty paragraphs, while `pypdf` extracts ordered native PDF pages. A PDF with zero blocks or fewer than 20 characters is marked `needs_ocr`, not silently accepted as text. Processing records retain parser name/version, duration, status, and a sanitized error summary.

- **Language:** Python 3.12 or newer within the supported dependency range.
- **Desktop UI:** PySide6 with Qt Widgets.
- **Persistence:** SQLite through SQLAlchemy, with Alembic migrations from the first schema.
- **Validation:** Pydantic models at application and provider boundaries.
- **Testing:** pytest, Qt-aware UI tests, and synthetic fixtures only.
- **Packaging:** `pyside6-deploy`/Nuitka as the initial self-contained application build path, followed by a Windows installer in the validation issue.

The normal user installs and launches one application. Python, Qt, and application dependencies are bundled; a browser, terminal, local HTTP server, and user-installed Python runtime are not part of the daily workflow.

## Desktop presentation

Qt Widgets is the Phase 1 UI technology. The interface is a case-centered desktop workspace with `Cases`, `Overview`, `Sources`, `Review`, and `Work` surfaces. The detailed interaction rules are in [ui-client.md](ui-client.md).

The UI is implemented as small widgets and view models over application services. Domain entities and business rules do not live in widgets, slots, or Qt-specific models. Qt's model/view APIs may adapt application read models for display but must not become the persistence model.

Qt Quick/QML, an embedded web frontend, and a separate JavaScript build system are not used in Phase 1. They may be reconsidered only if validated UI requirements cannot be met cleanly with Qt Widgets.

## Background execution

The default deployment is one application process, but the UI thread performs no long-running document or model work.

- Short application operations may execute synchronously.
- File extraction and model requests use an internal background-task boundary.
- `QThreadPool` or Qt workers are suitable initial implementations.
- CPU-heavy OCR or complex parsing may later use an internal worker process.
- The application owns every worker's lifecycle, progress, cancellation, failure reporting, and shutdown.

This process model is intentionally replaceable behind the execution boundary. It is not a commitment to keep every future workload in one process.

## Initial document support

Phase 1 uses focused in-process libraries:

- plain Python text handling for pasted text and TXT;
- `python-docx` for DOCX;
- `pypdf` for page-oriented text extraction from native PDFs;
- Qt PDF widgets for embedded PDF viewing where practical.

The goal is not perfect document understanding. The goal is reliable ingestion status, preserved originals, page-level source references, and a clean adapter boundary.

Scanned or poorly extracted PDFs are detected and marked `needs_ocr`. OCR is not silently attempted through an external GUI or subprocess-controlled application.

DOCX does not require a full fidelity embedded Word renderer in Phase 1. The client shows extracted text and can open the preserved original through the operating system without automating the external editor.

## OCR decision

No OCR engine is selected for Phase 1 implementation. Representative Chinese legal scans must first be used to compare candidates such as PaddleOCR and Docling-based pipelines for:

- Chinese text accuracy;
- page and reading-order preservation;
- installation size and Windows reliability;
- CPU performance;
- license compatibility;
- ability to return stable source coordinates.

The selected engine, if any, will be integrated as a library or internal adapter. End users will not be required to operate a separate OCR application.

## Model integration

The internal model boundary exposes one structured-generation operation with explicit request metadata and validated output.

Phase 1 implements one configurable OpenAI-compatible HTTP adapter. This is a protocol choice, not an OpenAI product commitment; it can cover several hosted services and local servers that expose the compatible API shape.

Native adapters for Claude, Gemini, OpenAI-specific features, or local runtimes are added only when selected models require them. The application will not begin with a general routing framework, automatic model selection, or a universal abstraction over every provider feature.

Provider names, prompt text, tokens, routing, and transport details are not part of the normal lawyer-facing interface. Configuration and diagnostics remain a separate owner/support concern.

## Context strategy

Phase 1 uses explicit source selection and a versioned Case Brief. It does not use embeddings or vector retrieval.

If real matters exceed direct context limits, a later benchmark must compare retrieval strategies against a full-context or manually selected baseline before a vector database is introduced.

## Workflow strategy

The first workflow is implemented in application code with versioned prompt and output schemas. It produces the Case Brief.

Only after at least two materially different legal tasks exist should the project extract a reusable workflow-definition format. This avoids designing a generic workflow engine from hypothetical requirements.

## DOCX output

DOCX is expected to become an important work-product format, with `python-docx` as the default starting library. It is deferred until Phase 1 establishes reviewed matter context and identifies the first concrete drafting workflow.

## Distribution and updates

The first validated private build must launch without a terminal, browser, development environment, or separately started service. Packaging tests happen early enough to catch missing Qt plugins and Python dependencies before the final usability issue.

A normal Windows installer, shortcut, uninstall path, and preserved application-data behavior are required for the completed Phase 1 vertical slice. Automatic updates and public-store distribution are deferred.

PySide6 and Qt distribution obligations must be reviewed and documented before the first distributable is handed to another user.

## Explicitly rejected for Phase 1

- a browser-based primary client or user-managed local web server;
- controlling consumer AI or OCR applications through shortcuts, screenshots, or GUI automation;
- putting domain or workflow logic inside Qt widgets;
- a separate React, Flutter, Electron, Tauri, or Flet client stack;
- vendoring a large third-party project before an integration benchmark;
- LangChain, LlamaIndex, or a multi-agent framework as foundational dependencies;
- a vector database, knowledge graph, Redis, Celery, or background service cluster;
- automatic cloud synchronization of private matter data.
