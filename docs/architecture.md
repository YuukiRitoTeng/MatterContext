# Architecture

## Status

This document defines the Phase 1 target architecture. The repository does not yet contain the implementation.

## Architectural objective

The application must make a legal matter durable across sessions while preserving the difference between raw sources, machine-derived proposals, and lawyer-reviewed information.

The architecture is intentionally a local modular monolith. A single process and a single database are easier to install, inspect, back up, and evolve than a collection of services. Internal boundaries are kept explicit so that parsers, model providers, workflows, and the user interface can change without rewriting the matter model.

## Runtime shape

```text
Local browser
    |
    v
Server-rendered web application
    |
    +--> Matter application services
    |       |
    |       +--> Domain model and review rules
    |       +--> Ingestion and extraction adapters
    |       +--> Model adapter
    |       +--> Case Brief workflow
    |
    +--> SQLite database
    +--> Local attachment directory
```

Phase 1 runs on one Windows computer for one user. It does not require a separate frontend development server, vector database, message broker, OCR application, or model-hosting process.

## Core boundaries

### Domain

Owns the concepts and invariants described in [domain-model.md](domain-model.md): matters, source records, claims, source references, review decisions, processing runs, and Case Brief versions.

The domain must not depend on a web framework, parser library, or model SDK.

### Application services

Coordinates user operations such as creating a matter, appending a narrative update, importing a document, reviewing a claim, and generating a Case Brief.

Application services enforce transaction boundaries and call infrastructure through small interfaces.

### Ingestion

Registers an input as a source before attempting extraction. Each source receives a stable identifier, content hash, media type, original filename when applicable, and creation timestamp.

Initial adapters handle pasted text, TXT, native-text PDF, and DOCX. Extraction results use a common page/block representation. A parser failure or insufficient PDF text produces an explicit status such as `needs_ocr` or `failed`; it must never be reported as successful empty content.

### AI

Provides a small internal model interface for structured generation. Phase 1 implements one configurable OpenAI-compatible HTTP adapter because it can serve several hosted and local providers. Provider-specific native adapters are added only when a real model choice requires them.

The model interface is not a router. It covers the minimum required operations, records the selected provider/model and prompt version, and returns validated structured output or an explicit failure.

### Workflows

Phase 1 implements one workflow: build or rebuild a Case Brief from selected matter sources and existing review decisions.

Later legal tasks may become versioned workflow definitions with context-selection rules, input/output schemas, and export behavior. No generic agent engine is required for Phase 1.

### Web interface

Provides a simple local interface for a non-technical user. The first interface needs matter selection, a matter overview, narrative update entry, document upload, processing status, claim review, and Case Brief viewing.

The UI calls application services; it does not write directly to SQLite or contain domain rules.

## Data flow

### Narrative update

1. The user pastes a new account, correction, or missing detail into a matter.
2. The exact submitted text is stored as an immutable source record.
3. A processing run may propose claims, events, parties, and open questions.
4. Proposed items are linked back to spans in that source.
5. Existing confirmed items are not overwritten. Potential conflicts remain visible for review.
6. A new Case Brief version may be generated from the updated state.

### Document import

1. The original file is hashed and copied into the matter attachment store.
2. Duplicate content is detected by hash without discarding the user's attempted import record.
3. The format adapter extracts page or block text when supported.
4. Extraction quality checks determine `ready`, `needs_ocr`, or `failed`.
5. AI processing, when requested, operates on extracted content and creates proposals with source references.
6. The original document and extraction metadata remain available for later reprocessing with a different parser.

## Persistence

SQLite stores matter metadata, source records, extracted blocks, claims, references, review decisions, processing runs, and Case Brief versions. Original files live in an application-managed local directory and are addressed from SQLite by stable relative paths.

Runtime data is never stored in the Git repository. Database migrations are required from the first implemented schema.

## Context assembly

Phase 1 does not use RAG or a vector database. The Case Brief workflow assembles context from explicit matter sources, reviewed claims, and bounded extracted text. Context limits must fail visibly or request a narrower source selection rather than silently dropping material.

Retrieval is introduced later only if representative matters exceed practical direct-context limits and a benchmark shows that retrieval improves the workflow without hiding relevant material.

## Safety and traceability rules

- Raw source records are immutable from the application layer.
- AI output cannot create a `confirmed` review state.
- Every proposed claim has at least one source reference or is explicitly marked as an unsupported inference.
- Regeneration creates a new version; it does not mutate a prior Case Brief.
- Outbound model calls are user-initiated and recorded with provider, model, workflow version, and included source identifiers.
- API keys are never stored in source control or exposed to browser-side code.
- Logs must not contain full matter text by default.

## Evolution path

If Phase 1 is useful, later additions can be made behind existing boundaries:

- OCR as another extraction adapter;
- native provider adapters;
- task-specific legal workflows;
- case-law research through a separately governed tool interface;
- DOCX export from reviewed workflow output;
- retrieval for matters that demonstrably require it;
- packaging that starts the local application from one Windows shortcut.

None of these changes requires replacing the matter, source, review, or versioning model.
