from __future__ import annotations

import pytest

from matter_context.domain import ActorKind, Provenance, ReviewDecision, ReviewState
from matter_context.domain.errors import UnauthorizedReviewError


def test_ai_cannot_impersonate_a_user_confirmation() -> None:
    with pytest.raises(UnauthorizedReviewError):
        ReviewDecision("review", "claim", ReviewState.CONFIRMED, ActorKind.AI, "model")


def test_ai_proposal_has_explicit_provenance_without_confirmation() -> None:
    decision = ReviewDecision("review", "claim", ReviewState.PROPOSED, ActorKind.AI, "model")

    assert decision.state is ReviewState.PROPOSED
    assert Provenance.AI_INFERRED.value == "ai_inferred"
