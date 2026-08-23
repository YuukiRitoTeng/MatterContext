"""Transactional SQLAlchemy unit of work."""

from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from .repositories import (
    SqlAlchemyCaseBriefRepository, SqlAlchemyClaimRepository, SqlAlchemyContentBlockRepository,
    SqlAlchemyMatterRepository, SqlAlchemyProcessingRunRepository, SqlAlchemyReviewRepository,
    SqlAlchemySourceReferenceRepository, SqlAlchemySourceRepository,
)


class SqlAlchemyUnitOfWork:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory
        self.session: Session | None = None

    def __enter__(self) -> "SqlAlchemyUnitOfWork":
        self.session = self._session_factory()
        self.matters = SqlAlchemyMatterRepository(self.session)
        self.sources = SqlAlchemySourceRepository(self.session)
        self.content_blocks = SqlAlchemyContentBlockRepository(self.session)
        self.claims = SqlAlchemyClaimRepository(self.session)
        self.source_references = SqlAlchemySourceReferenceRepository(self.session)
        self.reviews = SqlAlchemyReviewRepository(self.session)
        self.processing_runs = SqlAlchemyProcessingRunRepository(self.session)
        self.case_briefs = SqlAlchemyCaseBriefRepository(self.session)
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        assert self.session is not None
        if exc_type is not None:
            self.rollback()
        self.session.close()

    def commit(self) -> None:
        assert self.session is not None
        self.session.commit()

    def rollback(self) -> None:
        assert self.session is not None
        self.session.rollback()
