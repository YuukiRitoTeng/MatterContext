# Product Scope

## Primary user and environment

The initial product is for a lawyer with ordinary computer skills who works on a Windows computer and already uses consumer speech-to-text or AI applications for case narration.

The user should not need to understand prompt engineering, retrieval architecture, model APIs, or document-processing tools. The product owner may configure the application and model credentials, but normal matter work must happen through a simple interface.

## Core job to be done

> When I return to a legal matter or start a new task within it, help me continue from the accumulated case background without making me explain the entire matter again, while showing me what the system believes and where that information came from.

## Problem decomposition

The first problem is not general legal reasoning. It is continuity and controlled accumulation:

- an initial account is incomplete;
- later updates add, correct, or contradict earlier information;
- documents provide additional statements and evidence;
- AI-derived structure can be useful but can also collapse uncertainty;
- a reusable matter context must remain reviewable over time.

## Phase 1 user journey

1. Launch the installed Windows desktop application from its normal shortcut.
2. Create a matter or select an existing one.
3. Paste an initial case account.
4. Return later and append another account, correction, or clarification.
5. Import a supported document and see whether extraction succeeded.
6. Generate proposed parties, claims, events, and open questions.
7. Review important proposals as confirmed, disputed, or rejected.
8. Open the latest Case Brief and inspect its source references.
9. Close and reopen the application without losing matter state.

The daily workflow must not require a browser, terminal, Python installation, local-server command, or separately operated processing application. See [ui-client.md](ui-client.md) for the Phase 1 information architecture.

## Phase 1 output: Case Brief

The Case Brief is an internal working context, not a pleading or legal opinion. It should contain:

- matter identity and short description;
- parties and relevant people;
- reviewed facts and material statements;
- chronology;
- disputed or contradictory information;
- available source materials;
- missing information and follow-up questions;
- source references for material entries;
- generation time and version.

The brief may be viewed in the application and exported to a simple machine-readable or Markdown representation. DOCX legal work product is intentionally deferred until the matter context itself is reliable.

## User confirmation policy

The application should minimize review burden without pretending that all model output is reliable.

- Raw narrative updates and documents require no line-by-line confirmation to be stored.
- AI-derived claims begin as `proposed`.
- The user can confirm, dispute, or reject material claims individually or in a clear batch operation.
- Only a user action can produce a `confirmed` state.
- A later source may create a conflict but cannot silently demote or replace an earlier decision.
- Review decisions record who made the decision, when, and against which claim version.

## Phase 1 acceptance boundary

Phase 1 is complete only when the full user journey works through the packaged desktop client with persistent local data and synthetic test fixtures. A collection of parser functions, prompts, command-line demos, or browser-only development pages is not sufficient.

## Deferred product questions

The following require evidence from the Phase 1 users before implementation:

- whether scanned documents are common enough to justify local OCR packaging;
- which first legal work product should follow the Case Brief;
- whether case-law research should use an MCP service, direct API, or another integration;
- whether local models are required for privacy or cost;
- whether matters become large enough to require retrieval;
- whether DOCX editing needs a built-in editor or export-only workflow.
