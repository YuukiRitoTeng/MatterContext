# Domain Model

## Purpose

The domain model preserves matter continuity and prevents generated summaries from becoming the sole record of a case.

This is a conceptual Phase 1 model. Exact table names may differ, but implementations must preserve the invariants below.

## Matter

The durable workspace for one legal matter.

Minimum attributes:

- stable identifier;
- title;
- optional matter reference and short description;
- status;
- created and updated timestamps.

A matter owns its sources, claims, review decisions, processing runs, and Case Brief versions.

## Source record

An immutable record of something supplied to the matter.

Source kinds in Phase 1:

- `narrative_update` for pasted accounts, corrections, and later additions;
- `document` for TXT, DOCX, and PDF files.

Minimum attributes:

- stable identifier and matter identifier;
- source kind;
- exact original text or attachment reference;
- content hash;
- original filename and media type when applicable;
- creation timestamp;
- ingestion and extraction status.

Editing an earlier narrative does not mutate the source. A correction is a new source record that can reference the earlier source.

## Content block

A normalized, addressable piece of extracted source content.

Examples include a pasted-text span, a DOCX paragraph, or a PDF page block. A block stores its order and source locator, such as page number, paragraph index, or character offsets.

Content blocks are parser output. They may be replaced by a later processing run without changing the original source record.

## Claim

An atomic proposition proposed for use in the matter context. A claim can represent a party, relationship, event, date, amount, allegation, document statement, or open question.

A claim records:

- normalized statement;
- claim category;
- provenance type, such as party account, attorney note, document statement, or model inference;
- current review state;
- source references;
- creation and supersession metadata.

The provenance type describes where a statement came from. It does not establish that the statement is true. A statement appearing in a document may still be an allegation.

## Source reference

Links a claim or Case Brief entry to an addressable part of a source.

Phase 1 references should support:

- source identifier;
- content block identifier;
- page or paragraph when available;
- character offsets when available;
- optional quoted excerpt for review convenience.

A reference proves traceability to an input location, not legal truth or evidentiary weight.

## Review decision

An append-only user decision about a claim.

Review states:

- `proposed`: generated or extracted and not yet reviewed;
- `confirmed`: accepted by the user for the current working context;
- `disputed`: material conflict or uncertainty remains;
- `rejected`: should not be used as a matter fact;
- `superseded`: replaced by a newer reviewed formulation without deleting history.

Only a user action can confirm, dispute, or reject a claim. A processing run cannot create those states.

## Processing run

Records a parser or model operation and makes derived results reproducible enough to inspect.

Minimum metadata:

- operation type;
- input source identifiers;
- parser or provider/model identifier;
- workflow and prompt version;
- start and completion timestamps;
- success, failure, or partial status;
- error summary without full sensitive input text.

## Case Brief version

An immutable snapshot assembled from the matter at a point in time.

Each version records:

- included source identifiers;
- included claim and review-decision versions;
- workflow version;
- structured brief payload;
- human-readable rendering;
- creation timestamp.

Generating a new brief never overwrites an earlier version.

## Required invariants

1. Original sources are never silently rewritten by AI processing.
2. Generated claims cannot become confirmed without user action.
3. Contradictory claims may coexist and must remain visible.
4. A claim without a source is labeled as an inference or missing-source item.
5. Derived content can be regenerated without losing source or review history.
6. Deleting or archiving a matter is an explicit user operation and is not part of automated processing.
