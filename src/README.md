# Source Layout

No application code has been implemented yet. Phase 1 issues will create one Python package under `src/matter_context/`.

The intended internal layout is:

```text
src/matter_context/
├── domain/       # Framework-independent matter model and invariants
├── application/  # Use cases and transaction coordination
├── storage/      # SQLite repositories, migrations, and attachment storage
├── ingestion/    # Text, TXT, DOCX, and native-PDF adapters
├── ai/           # Minimal model interface and provider adapters
├── workflows/    # Versioned Case Brief workflow
├── execution/    # Internal background-task and worker boundaries
├── ui/           # PySide6 presentation, view models, and desktop resources
└── export/       # Machine-readable and human-readable exports
```

This is a modular monolith, not a set of deployable services. The `ui` package may depend on application services; domain, application, storage, ingestion, AI, and workflow code must not depend on Qt widgets. Directories should be created when their first implementation is added, rather than maintained as empty placeholders.
