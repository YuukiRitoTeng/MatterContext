# Dependency and Source-Reuse Policy

## Objective

MatterContext should reuse mature software without becoming a fragile controller for external applications or acquiring unclear licensing obligations.

## Preferred order

1. Use a maintained package through its public API.
2. Wrap it behind a small MatterContext adapter.
3. Contribute required fixes upstream when practical.
4. Vendor a narrowly scoped source component only when the package form is unsuitable and the license clearly permits reuse.
5. Reimplement only when available options are unreliable, incompatible, or disproportionately complex.

## Runtime integration rules

- Normal users should not need to start or coordinate multiple independent applications.
- GUI automation, keyboard shortcuts, screen scraping, and clipboard control are not acceptable runtime integration mechanisms.
- Internal threads or worker processes are acceptable when the installed application owns their complete lifecycle and reports failures through the same desktop UI.
- Optional local model servers may be supported later, but failure to start them must be explicit and recoverable.
- Every parser, OCR engine, model provider, and export implementation sits behind an internal adapter with tests.

## License rules

- Prefer permissive licenses such as MIT, BSD, and Apache-2.0.
- Review transitive and model-weight licenses, not only the top-level repository license.
- Avoid copyleft dependencies when an equivalent permissive option exists and distribution obligations are not intentionally accepted.
- Do not copy source from a repository without recording its origin, exact revision, license, local modifications, and required notices.
- Keep third-party notices with the distributed application when licenses require them.

## Planned package use

The initial direction favors package dependencies rather than copied source:

- PySide6 and Qt Widgets for the desktop presentation layer;
- SQLAlchemy, Alembic, Pydantic, and pytest for the application foundation;
- pypdf for native PDF text extraction;
- python-docx for DOCX input and later output;
- an HTTP client for the first model adapter.

OCR candidates are evaluation targets, not approved runtime dependencies yet. Docling is attractive for broad parsing and local execution, and PaddleOCR is attractive for Chinese OCR, but either could add material package size and operational complexity. Selection requires a sample-based decision record.

## Required record when vendoring source

Any future vendored component must add an entry containing:

- component and upstream repository;
- upstream commit or release;
- license and copyright notice;
- files copied;
- modifications made;
- reason a normal dependency was not used;
- update and security-monitoring plan.

No third-party source is vendored in the repository at the current stage.
