# MatterContext

A local-first, matter-centered AI workspace for legal work.

## Why this project exists

Generic AI conversations start with an empty context. A lawyer may explain a case, remember an omitted fact, add another document, and then repeat much of the same background the next time a different legal task begins.

MatterContext treats the legal matter—not a chat session or a file—as the durable unit of work. Each matter keeps its source materials, later narrative updates, review decisions, and generated work context together so that the lawyer can build on prior work without repeatedly reconstructing the case.

The project is initially a private tool for a small number of real users. It is not currently intended to be a general-purpose commercial LegalTech platform.

## Product definition

MatterContext helps a lawyer:

1. create or reopen a matter;
2. add narrative updates over time, including text copied from an external speech-to-text tool;
3. attach supported case documents;
4. preserve every input as an identifiable source;
5. turn those sources into a reviewable, versioned Case Brief;
6. reuse the reviewed matter context in later legal workflows.

The system must not silently turn an allegation, recollection, document statement, or model inference into a confirmed fact. AI-generated structure is a proposal for review, not an authoritative rewrite of the matter.

## Phase 1

Phase 1 delivers one complete local workflow:

```text
Create matter
    -> add narrative updates and native-text documents
    -> preserve source records
    -> propose structured claims and open questions
    -> review important claims
    -> generate a versioned Case Brief with source references
```

The first supported inputs are intentionally narrow:

- pasted plain text, including speech-to-text copied from another application;
- `.txt` files;
- `.docx` files;
- PDFs that already contain extractable text.

Image-only and poorly extracted documents must be reported as requiring OCR rather than being treated as empty or successfully processed. OCR implementation will be selected only after testing real representative samples.

## Phase 1 success criteria

The first phase is useful when a non-technical lawyer can:

- install and launch one Windows desktop application without opening a terminal or browser;
- reopen a matter and understand its current state without retelling it;
- add a correction or missing detail without losing the original account;
- see where important statements came from;
- distinguish proposed, confirmed, disputed, and rejected information;
- regenerate the Case Brief without overwriting prior sources or review decisions.

## Deliberate non-goals

Phase 1 does not include:

- built-in speech recognition;
- OCR implementation, handwriting recognition, seal recognition, or advanced table extraction;
- a legal research database or case-law retrieval service;
- RAG, a vector database, a knowledge graph, or a multi-agent system;
- automated legal advice or unattended legal decision-making;
- a complete library of pleading and drafting workflows;
- DOCX work-product generation;
- a large multi-provider routing framework;
- a browser-based primary client or user-managed local web server;
- cloud multi-tenancy, collaboration, billing, or enterprise administration.

These capabilities may be considered later only when a working matter-centered workflow demonstrates a concrete need for them.

## Engineering principles

- **Matter first.** Files, notes, analysis, and outputs belong to a matter.
- **Sources before summaries.** Raw inputs remain available and identifiable.
- **Append, do not erase.** Later updates and corrections do not rewrite history.
- **Human confirmation is explicit.** Models may propose; only the user confirms.
- **Local first.** Matter data is stored locally by default, and outbound model calls are explicit.
- **One application experience.** Internal workers may exist, but the user never coordinates services or companion applications.
- **Provider-flexible, not router-heavy.** A small model interface prevents hard lock-in without predicting every provider.
- **Reuse mature libraries.** Prefer well-maintained, license-compatible dependencies over fragile external application automation or unnecessary reimplementation.
- **Simple but durable.** The shortest implementation path must still support migrations, tests, traceability, and later growth.

## Planned technical direction

Phase 1 is a Windows desktop application built with Python, PySide6, and Qt Widgets. The presentation layer calls framework-independent application services; domain and workflow logic does not live in Qt widgets. SQLite stores metadata, attachments stay in an application-managed local directory, and background work remains internal to the application. Native-text parsing uses focused libraries instead of a separate document-processing application. See:

- [Product scope](docs/product-scope.md)
- [Desktop client and UI](docs/ui-client.md)
- [Architecture](docs/architecture.md)
- [Domain model](docs/domain-model.md)
- [Technology decisions](docs/technology-decisions.md)
- [Dependency and source-reuse policy](docs/dependency-policy.md)

## Status

The desktop shell foundation is available. It starts at `Cases` and intentionally shows an empty state until matter persistence is implemented.

## Development setup

MatterContext requires Python 3.12 or newer and PowerShell 7 on Windows. From a fresh checkout:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m pytest
python -m matter_context
```

The installed desktop entry point is also available after installation:

```powershell
matter-context --smoke-test
matter-context --check-model-connection
```

`--smoke-test` starts the Qt application and exits promptly. It is used for automated checks and does not open a browser, start an HTTP listener, or require any separately managed service.

## Structured generation

Model configuration is owner-only through the blank `MATTER_CONTEXT_MODEL_*` environment variables in `.env.example`; credentials are never stored in the matter database or normal UI state. With all three connection values blank, MatterContext uses its deterministic offline fake. `--check-model-connection` sends a fixed synthetic payload only. Matter content is sent only after the lawyer clicks **Organize selected source**; that versioned `organized-update/v1` workflow records an audit `ProcessingRun` but cannot change sources, claims, reviews, or Case Briefs. Invalid structured output, refusals, timeout, rate limit, and temporary server failures show sanitized actionable feedback.

## Document ingestion

Sources accepts UTF-8 TXT, DOCX, and native-text PDF files up to 50 MiB. Originals are copied into the local managed attachment store before background extraction. TXT character ranges, DOCX one-based paragraphs, and PDF one-based pages are persisted as content blocks. PDFs with no text or fewer than 20 extracted characters are marked `needs_ocr`; OCR itself is deliberately out of scope.

## Runtime data and packaging smoke

Runtime configuration, databases, attachments, caches, and diagnostics are created outside the checkout. By default they use the platform application-data locations; tests and managed deployments may set `MATTER_CONTEXT_CONFIG_DIR`, `MATTER_CONTEXT_DATA_DIR`, `MATTER_CONTEXT_ATTACHMENTS_DIR`, `MATTER_CONTEXT_CACHE_DIR`, and `MATTER_CONTEXT_DIAGNOSTICS_DIR` to isolated locations. Never put credentials in `.env.example` or source control.

Build and launch the early Windows standalone smoke artifact with:

```powershell
python -m pip install -e ".[package]"
pwsh -File .\scripts\build-smoke.ps1
```

This invokes the PySide6/Nuitka deployment path and runs the produced executable directly with `--smoke-test`; it is not an installer or updater.

MatterContext is assistive software. It does not replace a qualified lawyer's professional judgment, source verification, or responsibility for legal work.
