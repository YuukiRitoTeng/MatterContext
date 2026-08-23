# Tests

Phase 1 tests will cover:

- domain invariants and review-state transitions;
- SQLite persistence and migrations;
- extraction adapters and explicit failure states;
- provider-response validation;
- Case Brief versioning and source references;
- PySide6 view-model and primary desktop interaction behavior;
- background-task completion, cancellation, and failure reporting;
- a packaged Windows application smoke test;
- the complete local user journey.

Only synthetic or explicitly cleared fixtures may be committed. Real client or matter data must never be added to the repository, test output, snapshots, or issue attachments.
# Test Layout

The suite uses isolated SQLite files and transactional unit-of-work tests. Persistence tests cover append-only sources, explicit AI provenance, user-only reviewed states, claim revisions, reopening, attachment containment, and fresh Alembic upgrades.
