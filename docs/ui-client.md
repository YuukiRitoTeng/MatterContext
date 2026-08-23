# Desktop Client and UI

## Confirmed decision

Phase 1 is a Windows desktop application built with PySide6 and Qt Widgets.

The product is a local-first, single-application, matter-centered workspace. A normal user installs and launches MatterContext without opening a browser, terminal, Python environment, local web server, or separately operated processing application.

Qt is the presentation layer. Widgets call application services and display application state; they do not own domain invariants, persistence rules, document-processing logic, model requests, or workflow definitions.

## Product shell

MatterContext uses one primary window. The initial top-level destination is `Cases`, not a chat screen.

```text
Cases
└── Matter workspace
    ├── Overview
    ├── Sources
    ├── Review
    └── Work
```

The matter header keeps the matter title, optional reference, status, `Add case update`, and `Add files` visible. `Work` contains the current Case Brief action and its output versions. Additional legal workflows appear there only after they have concrete requirements.

## Phase 1 surfaces

### Cases

- list and search existing matters;
- show recent and active matters;
- create a matter;
- reopen a matter without exposing storage paths or database concepts.

### Overview

- current reviewed matter summary;
- parties and people when available;
- chronology summary;
- recent sources and updates;
- pending-review and open-question counts;
- prominent entry points for adding a case update or files.

### Sources

- unified list of narrative updates and imported documents;
- drag-and-drop and native file selection;
- clear `processing`, `ready`, `needs text recognition`, and `failed` states;
- extracted-text preview for TXT and DOCX;
- embedded PDF preview when practical, with source-page navigation;
- an option to open the preserved original in its registered desktop application without controlling that application.

### Review

- proposed claims, possible conflicts, and open questions;
- supporting source excerpt beside the item being reviewed;
- explicit confirm, dispute, reject, and supersede actions;
- no automatic replacement of earlier sources or review decisions.

### Work

- Phase 1 exposes one task: create or update the Case Brief;
- show progress, actionable failures, and the source selection in user language;
- list immutable Case Brief versions;
- view and export supported outputs.

## Add case update

`Add case update` is a primary matter action, not a chat message.

The input supports an initial account, later information, a correction, or an attorney note. The exact submitted text is saved first as an immutable source. A correction may reference an earlier source but never edits it in place.

The practical voice-input flow is intentionally external and simple:

```text
Attorney speaks using a voice-input tool
    -> transcription
    -> copy and paste into MatterContext
    -> save as a case update
    -> process the update
    -> send relevant proposals to Review
```

Built-in speech recognition and automation of the external voice-input application are not part of Phase 1.

## AI presentation

Phase 1 has no general-purpose chat home page. Model operations appear as product actions such as `Organize update`, `Review new information`, and `Update Case Brief`.

If matter-scoped conversation is added later, it remains secondary. A conversation cannot silently mutate sources or confirmed matter context; information intended for reuse must enter through a source or review operation.

Normal users must not see prompt text, token counts, temperature, model routing, MCP, agent terminology, OCR-provider names, raw JSON, database paths, internal ports, or Python environment details. Errors use task language and offer a next action. Sanitized technical diagnostics may exist under a support-only surface.

## Responsiveness and process ownership

The Phase 1 default is one application process. Fast operations may run directly through application services. Document extraction and model calls run outside the UI thread through a small background-execution boundary.

Qt workers, `QThreadPool`, asynchronous background tasks, and internally managed worker processes are valid implementation choices. A heavy OCR or parser operation may move to an internal process later. The desktop application must start, monitor, stop, and report that worker; the user never manages it as a separate program.

## Deliberate UI non-goals

- a rich-text or Office replacement editor;
- advanced PDF annotation;
- multiple application windows;
- a plugin or workflow marketplace;
- a prompt, agent, model, or OCR configuration console for the normal user;
- a general chat-first experience;
- elaborate animation or a custom theme system;
- automatic updates in the first validated private build.

## Accessibility and desktop behavior

The primary path must support keyboard focus, readable Chinese text, standard Windows scaling, clear disabled and progress states, and confirmation before destructive actions. The application must remain usable at common laptop resolutions without requiring a maximized window.
