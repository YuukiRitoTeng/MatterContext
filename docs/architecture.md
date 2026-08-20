# Architecture

## Phase 1 pipeline

```text
Raw Material → Ingestion → Parser → Converter → Knowledge Package → AI Reading
```

The initial architecture separates material intake, format parsing, semantic conversion, and prompt/readiness concerns so that future implementations can evolve independently.

## Module responsibilities

- `src/ingestion/`: receive and register source materials.
- `src/parser/`: extract content and metadata from source formats.
- `src/converter/`: normalize extracted content into a case knowledge package.
- `src/prompt/`: document prompts and AI-reading conventions.

No model API, RAG, legal database, agent workflow, or frontend is implemented in this phase.
