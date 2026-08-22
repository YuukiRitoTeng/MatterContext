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
- cloud multi-tenancy, collaboration, billing, or enterprise administration.

These capabilities may be considered later only when a working matter-centered workflow demonstrates a concrete need for them.

## Engineering principles

- **Matter first.** Files, notes, analysis, and outputs belong to a matter.
- **Sources before summaries.** Raw inputs remain available and identifiable.
- **Append, do not erase.** Later updates and corrections do not rewrite history.
- **Human confirmation is explicit.** Models may propose; only the user confirms.
- **Local first.** Matter data is stored locally by default, and outbound model calls are explicit.
- **Provider-flexible, not router-heavy.** A small model interface prevents hard lock-in without predicting every provider.
- **Reuse mature libraries.** Prefer well-maintained, license-compatible dependencies over fragile external application automation or unnecessary reimplementation.
- **Simple but durable.** The shortest implementation path must still support migrations, tests, traceability, and later growth.

## Planned technical direction

Phase 1 is planned as a Python application with a local server-rendered web interface, SQLite metadata storage, and a local attachment directory. Native-text parsing uses focused libraries instead of a separate document-processing application. See:

- [Product scope](docs/product-scope.md)
- [Architecture](docs/architecture.md)
- [Domain model](docs/domain-model.md)
- [Technology decisions](docs/technology-decisions.md)
- [Dependency and source-reuse policy](docs/dependency-policy.md)

## Status

Repository repositioning stage. No working application or production legal workflow has been implemented yet.

MatterContext is assistive software. It does not replace a qualified lawyer's professional judgment, source verification, or responsibility for legal work.
