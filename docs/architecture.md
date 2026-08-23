# Architecture

## Status

This document defines the Phase 1 target architecture. The repository does not yet contain the implementation.

## Architectural objective

The application must make a legal matter durable across sessions while preserving the difference between raw sources, machine-derived proposals, and lawyer-reviewed information.

The architecture is a local modular monolith delivered as one Windows desktop application. Phase 1 defaults to one application process, one SQLite database, and one application-managed attachment directory. Internal boundaries remain explicit so that presentation, parsers, model providers, workflows, and execution strategies can evolve without replacing the matter model.

The one-process default is an implementation choice, not a permanent constraint. Heavy work may move to an internally managed worker process when evidence justifies it. To the user, MatterContext remains one installed application with no separately operated services.

## Runtime shape

```text
PySide6 / Qt Widgets desktop window
    |
    v
Presentation and view models
    |
    v
Matter application services
    |
    +--> Domain model and review rules
    +--> Ingestion and extraction adapters
    +--> Model adapter
    +--> Case Brief workflow
    +--> Background-execution boundary
    |
    +--> SQLite database
    +--> Local attachment directory
```

Phase 1 runs on one Windows computer for one user. It does not require a browser, local HTTP server, frontend development server, terminal, user-installed Python runtime, message broker, OCR application, or user-managed model process.

## Dependency direction

```text
ui -> application -> domain
                 -> ports

storage, ingestion, ai, workflows, and execution implement or call ports
```

Qt types stop at the presentation boundary. Domain entities, application commands, repositories, parsers, provider adapters, and workflow schemas must remain usable in tests without creating a `QApplication`.

## Core boundaries

### Domain

Owns the concepts and invariants described in [domain-model.md](domain-model.md): matters, source records, claims, source references, review decisions, processing runs, and Case Brief versions.

The domain must not depend on Qt, a parser library, a persistence framework, or a model SDK.

### Application services

Coordinates user operations such as creating a matter, appending a case update, importing a document, reviewing a claim, and generating a Case Brief.

Application services enforce transaction boundaries and call infrastructure through small interfaces. They return application results and errors rather than manipulating widgets directly.

### Desktop presentation

PySide6 and Qt Widgets provide the single-window desktop client defined in [ui-client.md](ui-client.md).

The presentation layer owns navigation, dialogs, view models, user input, progress display, and mapping typed application results into user-facing language. It does not write directly to SQLite, invoke parser libraries directly, or decide review-state transitions.

### Background execution

Document extraction and model requests must not block the Qt UI thread. Application use cases submit work through a small execution boundary that reports progress, completion, cancellation, and typed failure.

Qt workers, `QThreadPool`, and asynchronous tasks are valid Phase 1 implementations. CPU-heavy OCR or complex parsing may later use an internal worker process. The desktop application owns worker startup, shutdown, crash handling, and diagnostics; no worker is a separately operated product.

### Ingestion

Registers an input as a source before attempting extraction. Each source receives a stable identifier, content hash, media type, original filename when applicable, and creation timestamp.

Initial adapters handle pasted text, TXT, native-text PDF, and DOCX. Extraction results use a common page/block representation. A parser failure or insufficient PDF text produces an explicit status such as `needs_ocr` or `failed`; it must never be reported as successful empty content.

### AI

Provides a small internal model interface for structured generation. Phase 1 implements one configurable OpenAI-compatible HTTP adapter because it can serve several hosted and local providers. Provider-specific native adapters are added only when a real model choice requires them.

The model interface is not a router. It covers the minimum required operations, records the selected provider/model and prompt version, and returns validated structured output or an explicit failure.

### Workflows

Phase 1 implements one workflow: build or rebuild a Case Brief from selected matter sources and existing review decisions.

Later legal tasks may become versioned workflow definitions with context-selection rules, input/output schemas, and export behavior. No generic agent engine is required for Phase 1.

## Data flow

### Case update

1. The user pastes a new account, correction, or attorney note into the matter workspace.
2. The exact submitted text is stored as an immutable source record.
3. A background processing run may propose claims, events, parties, and open questions.
4. Proposed items are linked back to spans in that source.
5. Existing confirmed items are not overwritten. Potential conflicts remain visible in Review.
6. A new Case Brief version may be generated from the updated state.

### Document import

1. The desktop client accepts native file selection or drag-and-drop.
2. The original file is hashed and copied into the matter attachment store.
3. Duplicate content is detected by hash without discarding the attempted import record.
4. A background adapter extracts page or block text when supported.
5. Extraction quality checks determine `ready`, `needs_ocr`, or `failed`.
6. AI processing, when requested, operates on extracted content and creates proposals with source references.
7. The original document and extraction metadata remain available for preview and later reprocessing.

## Persistence

SQLite stores matter metadata, source records, extracted blocks, claims, references, review decisions, processing runs, and Case Brief versions. Original files live in an application-managed local directory and are addressed from SQLite by stable relative paths.

Runtime data is never stored in the Git repository. Database migrations are required from the first implemented schema. UI state that has no domain meaning must not be mixed into matter records.

## Context assembly

Phase 1 does not use RAG or a vector database. The Case Brief workflow assembles context from explicit matter sources, reviewed claims, and bounded extracted text. Context limits must fail visibly or request a narrower source selection rather than silently dropping material.

Retrieval is introduced later only if representative matters exceed practical direct-context limits and a benchmark shows that retrieval improves the workflow without hiding relevant material.

## Safety and traceability rules

- Raw source records are immutable from the application layer.
- AI output cannot create a `confirmed` review state.
- Every proposed claim has at least one source reference or is explicitly marked as an unsupported inference.
- Regeneration creates a new version; it does not mutate a prior Case Brief.
- Outbound model calls are user-initiated and recorded with provider, model, workflow version, and included source identifiers.
- API keys are never stored in source control, exposed through normal UI state, or written to matter data.
- Logs must not contain full matter text by default.
- Worker failures must return to the desktop client as actionable, sanitized errors.

## Evolution path

If Phase 1 is useful, later additions can be made behind existing boundaries:

- OCR as another extraction adapter, potentially in an internal worker process;
- native provider adapters;
- task-specific legal workflows;
- case-law research through a separately governed tool interface;
- DOCX export from reviewed workflow output;
- retrieval for matters that demonstrably require it;
- signed installers and managed application updates.

None of these changes requires replacing the matter, source, review, versioning, or presentation-boundary rules.
