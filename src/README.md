# Source Layout

The package contains the Issue #3 desktop foundation and Issue #4 framework-independent domain, SQLite persistence, Alembic migration, and attachment storage. Runtime data is located through `application.runtime_paths`, never in the checkout.

The intended internal layout is:

```text
src/matter_context/
├── domain/       # Immutable matter records, provenance, and review invariants
├── application/  # Use cases, revision rules, and transaction coordination
├── storage/      # SQLite repositories, Alembic migrations, and attachment storage
├── execution/    # Internal background-task and worker boundaries
├── ui/           # PySide6 presentation, view models, and desktop resources
└── (future packages are introduced by their owning Phase 1 issues)
```

This is a modular monolith, not a set of deployable services. The `ui` package may depend on application services; domain, application, storage, ingestion, AI, and workflow code must not depend on Qt widgets. Directories should be created when their first implementation is added, rather than maintained as empty placeholders.

Document ingestion is local-only: validation permits TXT, DOCX, and PDF files up to 50 MiB, preserves originals under runtime attachments, and records parser metadata plus durable extraction status.

# MatterContext package

Structured generation is provider-neutral and owner-configured exclusively through `MATTER_CONTEXT_MODEL_*` environment values. The workspace exposes only an explicit selected-source organization action; its `organized-update/v1` result is display-only and processing metadata never includes API keys.
