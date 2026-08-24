from __future__ import annotations

import pytest

from matter_context.domain import ActorKind, ProcessingRun, ProcessingStatus, Provenance, ReviewDecision, ReviewState
from matter_context.domain.errors import DomainInvariantError, ProcessingRunTransitionError, UnauthorizedReviewError


def test_ai_cannot_impersonate_a_user_confirmation() -> None:
    with pytest.raises(UnauthorizedReviewError):
        ReviewDecision("review", "claim", ReviewState.CONFIRMED, ActorKind.AI, "model")


def test_ai_proposal_has_explicit_provenance_without_confirmation() -> None:
    decision = ReviewDecision("review", "claim", ReviewState.PROPOSED, ActorKind.AI, "model")

    assert decision.state is ReviewState.PROPOSED
    assert Provenance.AI_INFERRED.value == "ai_inferred"


def test_processing_run_requires_complete_terminal_states_and_one_way_transitions() -> None:
    running = ProcessingRun.start("run", "matter", "document_ingestion", ("source",))

    assert running.status is ProcessingStatus.RUNNING
    assert running.completed_at is None
    with pytest.raises(DomainInvariantError):
        ProcessingRun("invalid", "matter", "operation", (), ProcessingStatus.RUNNING, completed_at=running.started_at)
    with pytest.raises(DomainInvariantError):
        ProcessingRun("invalid", "matter", "operation", (), ProcessingStatus.SUCCEEDED)
    with pytest.raises(DomainInvariantError):
        ProcessingRun("invalid", "matter", "operation", (), ProcessingStatus.FAILED, completed_at=running.started_at)

    succeeded = running.succeed()
    partial = running.complete_partially()
    failed = running.fail("Safe failure summary")

    assert succeeded.status is ProcessingStatus.SUCCEEDED and succeeded.completed_at is not None
    assert partial.status is ProcessingStatus.PARTIAL and partial.completed_at is not None
    assert failed.status is ProcessingStatus.FAILED and failed.completed_at is not None
    with pytest.raises(ProcessingRunTransitionError):
        succeeded.complete_partially()
