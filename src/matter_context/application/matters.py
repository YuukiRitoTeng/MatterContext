"""Commands that preserve source, review, and revision history."""

from __future__ import annotations

from hashlib import sha256
from uuid import uuid4

from matter_context.domain import (
    ActorKind, Claim, Matter, NarrativeUpdateType, Provenance, ReviewDecision, ReviewState, SourceKind,
    SourceRecord, SourceReference,
)
from matter_context.domain.errors import DomainInvariantError, SourceMutationError

from .persistence import UnitOfWorkFactory


def new_identifier() -> str:
    return str(uuid4())


def payload_hash(payload: bytes | str) -> str:
    return sha256(payload.encode("utf-8") if isinstance(payload, str) else payload).hexdigest()


def _require_source_in_matter(source: SourceRecord | None, matter_id: str, *, missing_message: str) -> SourceRecord:
    if source is None:
        raise DomainInvariantError(missing_message)
    if source.matter_id != matter_id:
        raise DomainInvariantError("Source belongs to a different matter")
    return source


class MatterService:
    """Application boundary for durable, append-only matter operations."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    def create_matter(self, title: str, *, reference: str | None = None, description: str | None = None) -> Matter:
        if not title.strip():
            raise DomainInvariantError("A case title is required")
        matter = Matter(identifier=new_identifier(), title=title, reference=reference, description=description)
        with self._uow_factory() as uow:
            uow.matters.add(matter)
            uow.commit()
        return matter

    def append_narrative(
        self, matter_id: str, text: str, *, provenance: Provenance = Provenance.ATTORNEY_PROVIDED,
        correction_of_id: str | None = None,
    ) -> SourceRecord:
        return self.append_narrative_update(
            matter_id, text, provenance=provenance, correction_of_id=correction_of_id,
            update_type=NarrativeUpdateType.CORRECTION if correction_of_id else NarrativeUpdateType.INITIAL_ACCOUNT,
        )

    def append_narrative_update(
        self, matter_id: str, text: str, *, update_type: NarrativeUpdateType,
        provenance: Provenance = Provenance.ATTORNEY_PROVIDED, correction_of_id: str | None = None,
    ) -> SourceRecord:
        """Append an immutable pasted update through the matter transaction boundary."""
        if not text.strip():
            raise DomainInvariantError("A case update cannot be empty")
        if update_type is NarrativeUpdateType.CORRECTION and correction_of_id is None:
            raise DomainInvariantError("A correction must reference an earlier source")
        if update_type is not NarrativeUpdateType.CORRECTION and correction_of_id is not None:
            raise DomainInvariantError("Only a correction may reference an earlier source")
        source = SourceRecord(
            identifier=new_identifier(), matter_id=matter_id, kind=SourceKind.NARRATIVE_UPDATE,
            provenance=provenance, payload_sha256=payload_hash(text), text=text,
            correction_of_id=correction_of_id, update_type=update_type,
        )
        with self._uow_factory() as uow:
            if correction_of_id is not None:
                _require_source_in_matter(
                    uow.sources.get(correction_of_id), matter_id,
                    missing_message="Correction target source does not exist",
                )
            uow.sources.add(source)
            uow.commit()
        return source

    def get_matter(self, matter_id: str) -> Matter | None:
        with self._uow_factory() as uow:
            return uow.matters.get(matter_id)

    def list_sources(self, matter_id: str) -> list[SourceRecord]:
        with self._uow_factory() as uow:
            return uow.sources.list_for_matter(matter_id)

    def register_document(
        self, matter_id: str, attachment_path: str, digest: str, *, original_filename: str,
        media_type: str | None = None, correction_of_id: str | None = None,
    ) -> SourceRecord:
        source = SourceRecord(
            identifier=new_identifier(), matter_id=matter_id, kind=SourceKind.DOCUMENT,
            provenance=Provenance.ORIGINAL_SOURCE, payload_sha256=digest,
            attachment_path=attachment_path, original_filename=original_filename, media_type=media_type,
            correction_of_id=correction_of_id,
        )
        with self._uow_factory() as uow:
            if correction_of_id is not None:
                _require_source_in_matter(
                    uow.sources.get(correction_of_id), matter_id,
                    missing_message="Correction target source does not exist",
                )
            uow.sources.add(source)
            uow.commit()
        return source

    def register_document_file(
        self, matter_id: str, payload_path: str, attachment_store: object, *,
        original_filename: str, media_type: str | None = None,
    ) -> SourceRecord:
        """Copy an original into the managed store before recording its stable path."""
        stored = attachment_store.store(payload_path)
        return self.register_document(
            matter_id, stored.relative_path, stored.sha256,
            original_filename=original_filename, media_type=media_type,
        )

    def replace_source_payload(self, source_id: str, _: str) -> None:
        """Reject mutable-source APIs; callers must append a correction instead."""
        raise SourceMutationError(f"Source {source_id} is immutable; append a correction source")

    def propose_claim(
        self, matter_id: str, statement: str, category: str, provenance: Provenance,
        *, source_id: str | None = None, actor_kind: ActorKind = ActorKind.AI,
    ) -> Claim:
        ai_provenance = (Provenance.AI_ORGANIZED, Provenance.AI_INFERRED)
        if actor_kind is ActorKind.AI and provenance not in ai_provenance:
            raise DomainInvariantError("AI actors may only create explicitly AI-provenanced claims")
        if actor_kind is ActorKind.SYSTEM and provenance is Provenance.ATTORNEY_PROVIDED:
            raise DomainInvariantError("System actors may not create attorney-provided claims")
        if actor_kind is ActorKind.USER and provenance is not Provenance.ATTORNEY_PROVIDED:
            raise DomainInvariantError("User actors may only create attorney-provided claims")
        claim = Claim(new_identifier(), matter_id, statement, category, provenance)
        decision = ReviewDecision(new_identifier(), claim.identifier, ReviewState.PROPOSED, actor_kind, actor_kind.value)
        with self._uow_factory() as uow:
            if source_id is not None:
                _require_source_in_matter(
                    uow.sources.get(source_id), matter_id,
                    missing_message="Source reference target does not exist",
                )
            uow.claims.add(claim)
            if source_id is not None:
                uow.source_references.add(SourceReference(new_identifier(), claim.identifier, source_id=source_id))
            uow.reviews.add(decision)
            uow.commit()
        return claim

    def review_claim(self, claim_id: str, state: ReviewState, *, user_id: str, note: str | None = None) -> ReviewDecision:
        if state not in {ReviewState.CONFIRMED, ReviewState.DISPUTED, ReviewState.REJECTED}:
            raise DomainInvariantError("review_claim only accepts confirmed, disputed, or rejected states")
        decision = ReviewDecision(new_identifier(), claim_id, state, ActorKind.USER, user_id, note)
        with self._uow_factory() as uow:
            if uow.claims.get(claim_id) is None:
                raise DomainInvariantError("Claim does not exist")
            uow.reviews.add(decision)
            uow.commit()
        return decision

    def revise_claim(
        self, claim_id: str, statement: str, *, user_id: str, category: str | None = None,
        provenance: Provenance = Provenance.ATTORNEY_PROVIDED,
    ) -> Claim:
        with self._uow_factory() as uow:
            prior = uow.claims.get(claim_id)
            if prior is None:
                raise DomainInvariantError("Claim does not exist")
            revised = Claim(new_identifier(), prior.matter_id, statement, category or prior.category, provenance, claim_id)
            uow.claims.add(revised)
            for reference in uow.source_references.list_for_claim(claim_id):
                uow.source_references.add(SourceReference(
                    new_identifier(), revised.identifier, reference.source_id, reference.content_block_id,
                    reference.page, reference.paragraph, reference.character_start, reference.character_end,
                    reference.excerpt,
                ))
            uow.reviews.add(ReviewDecision(new_identifier(), claim_id, ReviewState.SUPERSEDED, ActorKind.USER, user_id))
            uow.reviews.add(ReviewDecision(new_identifier(), revised.identifier, ReviewState.CONFIRMED, ActorKind.USER, user_id))
            uow.commit()
        return revised

    def current_review_state(self, claim_id: str) -> ReviewState | None:
        with self._uow_factory() as uow:
            decisions = uow.reviews.list_for_claim(claim_id)
        return max(decisions, key=lambda item: item.created_at).state if decisions else None

    def effective_claims(self, matter_id: str) -> list[Claim]:
        with self._uow_factory() as uow:
            claims = uow.claims.list_for_matter(matter_id)
        superseded = {claim.revision_of_id for claim in claims if claim.revision_of_id}
        return [claim for claim in claims if claim.identifier not in superseded]
