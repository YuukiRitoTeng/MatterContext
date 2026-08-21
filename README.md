# Legal Agent Material Processor

An AI-assisted preprocessing system for legal case materials.

## Project Overview

Legal Agent Material Processor is an infrastructure project designed for legal practice workflows.

Its goal is to transform large volumes of unstructured case materials into structured case knowledge that large language models (LLMs) can read, trace, and analyze more reliably.

This project is intended to serve as the material-processing foundation for a future legal AI agent system.

---

# Project Goals

Legal work often involves information from many different sources and formats, including:

- Attorney case narration
- Client chat records
- Word documents
- Contracts
- PDF case files
- Scanned documents
- Audio recordings

These materials are often:

- Inconsistently formatted
- Scattered across multiple sources
- Poorly structured
- Difficult to provide directly to AI systems

The project aims to answer one core question:

> How can raw legal materials be converted into a case package that an AI system can understand reliably?

---

# Current Development Stage

## Phase 1: Case Material Processing Layer

Current focus:

```text
Raw Materials
      |
      v
Material Parsing
      |
      v
Information Structuring
      |
      v
Markdown / Knowledge Package
      |
      v
AI Reading
```

---

# Planned Material Types

## 1. Attorney Case Narration

Possible sources:

- Conversations between an attorney and an AI assistant
- Attorney voice notes
- Free-form case descriptions

Processing goals:

Generate:

- Case summary
- Core keywords
- Party and person relationships
- Timeline
- Disputed issues
- Items requiring confirmation

---

## 2. Standard Electronic Documents

Examples:

- Word
- TXT
- Excel
- Electronic contracts

Goal:

Extract content and convert it into a unified representation.

---

## 3. PDF Files

### Native PDFs

Extract embedded text directly.

### Scanned PDFs

Convert image-based content through OCR.

Future capabilities may include:

- Image recognition
- Table extraction
- Seal and stamp recognition
- Handwriting recognition

---

## 4. Audio Materials

Examples:

- Client interview recordings
- Telephone recordings
- Meeting recordings

Processing flow:

```text
Audio -> Text
```

The system should also preserve:

- Timestamps
- Speaker information
- Links to the original source file

---

# AI Reading Design

Converted materials should not be treated as undifferentiated plain text.

The target output is a:

```text
Case Knowledge Package
```

A package may contain:

```text
Case Information

People and Party Relationships

Facts and Events

Timeline

Evidence List

Disputed Issues

Source Files

Questions Requiring Confirmation
```

---

# AI Prompt Design Goals

When an AI system reads case materials, it should distinguish between different information types.

## Confirmed Facts

Facts supported by documents or evidence.

## Party Statements

Statements provided by a client, party, witness, or other source that have not yet been independently verified.

## Evidence-Supported Information

Claims or facts that can be traced to a specific source.

## Unverified or Missing Information

Information that is incomplete, uncertain, contradictory, or requires follow-up.

The system should avoid:

- Fabricating facts
- Treating assumptions as confirmed information
- Misattributing or misquoting source materials

---

# Future Roadmap

## Phase 2: Case Understanding Agent

Potential capabilities:

- Case analysis
- Legal issue decomposition
- Key fact extraction

## Phase 3: Legal Research Agent

Potential capabilities:

- Statute and regulation research
- Similar-case retrieval
- Case law analysis

## Phase 4: Legal Document Generation Agent

Potential capabilities:

- Complaints and pleadings
- Statements of defense
- Legal opinions
- Other legal documents

---

# Project Principles

1. AI does not replace professional legal judgment.

2. Important conclusions must be traceable to their sources.

3. Facts, opinions, assumptions, and unverified claims must remain distinguishable.

4. Accuracy and traceability take priority over generation speed.

---

# Status

Project initialization stage.

The repository currently contains the initial architecture only. No production legal workflow has been implemented yet.
