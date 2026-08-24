from __future__ import annotations

import pytest

from matter_context.application.matters import MatterService, payload_hash
from matter_context.domain import ActorKind, CaseBriefVersion, ContentBlock, ProcessingRun, ProcessingStatus, Provenance, ReviewState
from matter_context.domain.errors import DomainInvariantError, ProcessingRunTransitionError, SourceMutationError
from matter_context.storage.database import Database, upgrade_database
from matter_context.storage.attachments import AttachmentStore
from matter_context.storage.unit_of_work import SqlAlchemyUnitOfWork


@pytest.fixture
def service(tmp_path):
    database_path = tmp_path / "matter.sqlite3"
    url = f"sqlite:///{database_path}"
    upgrade_database(url)
    database = Database.from_url(url)
    yield MatterService(lambda: SqlAlchemyUnitOfWork(database.session_factory)), database
    database.engine.dispose()


def test_matter_and_source_survive_reopening(service) -> None:
    app, database = service
    matter = app.create_matter("Contract dispute", reference="MC-1")
    source = app.append_narrative(matter.identifier, "Client reports a missed payment.")
    database.engine.dispose()
    reopened = Database.from_url(str(database.engine.url))
    with SqlAlchemyUnitOfWork(reopened.session_factory) as uow:
        loaded = uow.matters.get(matter.identifier)
        sources = uow.sources.list_for_matter(matter.identifier)

    assert loaded and loaded.reference == "MC-1"
    assert sources[0].identifier == source.identifier
    assert sources[0].payload_sha256 == payload_hash("Client reports a missed payment.")


def test_source_is_append_only_and_correction_preserves_prior_record(service) -> None:
    app, _ = service
    matter = app.create_matter("Matter")
    original = app.append_narrative(matter.identifier, "Amount is 100.")
    correction = app.append_narrative(matter.identifier, "Amount is 120.", correction_of_id=original.identifier)

    with pytest.raises(SourceMutationError):
        app.replace_source_payload(original.identifier, "Amount is 1.")
    assert correction.correction_of_id == original.identifier
    assert original.payload_sha256 == payload_hash("Amount is 100.")


def test_narrative_correction_cannot_cross_matters(service) -> None:
    app, _ = service
    matter = app.create_matter("Matter")
    other_matter = app.create_matter("Other matter")
    source = app.append_narrative(other_matter.identifier, "Other source")

    with pytest.raises(DomainInvariantError, match="different matter"):
        app.append_narrative(matter.identifier, "Invalid correction", correction_of_id=source.identifier)


def test_document_correction_cannot_cross_matters(service) -> None:
    app, _ = service
    matter = app.create_matter("Matter")
    other_matter = app.create_matter("Other matter")
    source = app.register_document(
        other_matter.identifier, "other.pdf", payload_hash(b"other"), original_filename="other.pdf",
    )

    with pytest.raises(DomainInvariantError, match="different matter"):
        app.register_document(
            matter.identifier, "correction.pdf", payload_hash(b"correction"),
            original_filename="correction.pdf", correction_of_id=source.identifier,
        )


@pytest.mark.parametrize("register", ["narrative", "document"])
def test_nonexistent_correction_target_is_rejected(service, register: str) -> None:
    app, _ = service
    matter = app.create_matter("Matter")

    with pytest.raises(DomainInvariantError, match="does not exist"):
        if register == "narrative":
            app.append_narrative(matter.identifier, "Invalid correction", correction_of_id="missing-source")
        else:
            app.register_document(
                matter.identifier, "correction.pdf", payload_hash(b"correction"),
                original_filename="correction.pdf", correction_of_id="missing-source",
            )


def test_nonexistent_claim_source_reference_is_rejected(service) -> None:
    app, _ = service
    matter = app.create_matter("Matter")

    with pytest.raises(DomainInvariantError, match="does not exist"):
        app.propose_claim(
            matter.identifier, "Claim with missing source", "fact", Provenance.AI_INFERRED,
            source_id="missing-source",
        )


def test_claim_source_reference_cannot_cross_matters(service) -> None:
    app, _ = service
    matter = app.create_matter("Matter")
    other_matter = app.create_matter("Other matter")
    source = app.append_narrative(other_matter.identifier, "Other source")

    with pytest.raises(DomainInvariantError, match="different matter"):
        app.propose_claim(
            matter.identifier, "Claim with foreign source", "fact", Provenance.AI_INFERRED,
            source_id=source.identifier,
        )


def test_conflicts_and_revisions_preserve_review_history(service) -> None:
    app, database = service
    matter = app.create_matter("Matter")
    first = app.propose_claim(matter.identifier, "Payment was made.", "event", Provenance.AI_INFERRED)
    conflict = app.propose_claim(matter.identifier, "Payment was not made.", "event", Provenance.AI_INFERRED)
    app.review_claim(first.identifier, ReviewState.CONFIRMED, user_id="lawyer")
    revised = app.revise_claim(first.identifier, "Payment was partially made.", user_id="lawyer")

    with SqlAlchemyUnitOfWork(database.session_factory) as uow:
        history = uow.reviews.list_for_claim(first.identifier)
    assert {claim.identifier for claim in app.effective_claims(matter.identifier)} == {revised.identifier, conflict.identifier}
    assert [decision.state for decision in history] == [ReviewState.PROPOSED, ReviewState.CONFIRMED, ReviewState.SUPERSEDED]
    assert app.current_review_state(revised.identifier) is ReviewState.CONFIRMED


@pytest.mark.parametrize("state", [ReviewState.PROPOSED, ReviewState.SUPERSEDED])
def test_review_claim_rejects_non_user_review_states(service, state: ReviewState) -> None:
    app, _ = service
    matter = app.create_matter("Matter")
    claim = app.propose_claim(matter.identifier, "A proposed statement", "fact", Provenance.AI_INFERRED)

    with pytest.raises(DomainInvariantError, match="only accepts"):
        app.review_claim(claim.identifier, state, user_id="lawyer")


@pytest.mark.parametrize("state", [ReviewState.CONFIRMED, ReviewState.DISPUTED, ReviewState.REJECTED])
def test_review_claim_accepts_user_review_states(service, state: ReviewState) -> None:
    app, _ = service
    matter = app.create_matter("Matter")
    claim = app.propose_claim(matter.identifier, "A proposed statement", "fact", Provenance.AI_INFERRED)

    decision = app.review_claim(claim.identifier, state, user_id="lawyer")

    assert decision.state is state


def test_repeated_revisions_preserve_each_claim_and_review_history(service) -> None:
    app, database = service
    matter = app.create_matter("Matter")
    first = app.propose_claim(matter.identifier, "Initial statement", "fact", Provenance.AI_INFERRED)
    app.review_claim(first.identifier, ReviewState.CONFIRMED, user_id="lawyer")
    second = app.revise_claim(first.identifier, "Second statement", user_id="lawyer")
    third = app.revise_claim(second.identifier, "Third statement", user_id="lawyer")

    with SqlAlchemyUnitOfWork(database.session_factory) as uow:
        claims = uow.claims.list_for_matter(matter.identifier)
        first_history = uow.reviews.list_for_claim(first.identifier)
        second_history = uow.reviews.list_for_claim(second.identifier)
        third_history = uow.reviews.list_for_claim(third.identifier)

    assert [(claim.identifier, claim.revision_of_id) for claim in claims] == [
        (first.identifier, None), (second.identifier, first.identifier), (third.identifier, second.identifier),
    ]
    assert [decision.state for decision in first_history] == [
        ReviewState.PROPOSED, ReviewState.CONFIRMED, ReviewState.SUPERSEDED,
    ]
    assert [decision.state for decision in second_history] == [ReviewState.CONFIRMED, ReviewState.SUPERSEDED]
    assert [decision.state for decision in third_history] == [ReviewState.CONFIRMED]
    assert [claim.identifier for claim in app.effective_claims(matter.identifier)] == [third.identifier]


def test_ai_actor_cannot_impersonate_attorney_provenance(service) -> None:
    app, _ = service
    matter = app.create_matter("Matter")

    with pytest.raises(DomainInvariantError, match="AI actors"):
        app.propose_claim(matter.identifier, "Attorney statement", "fact", Provenance.ATTORNEY_PROVIDED, actor_kind=ActorKind.AI)


def test_failed_unit_of_work_rolls_back_all_records(service) -> None:
    _, database = service
    with pytest.raises(RuntimeError):
        with SqlAlchemyUnitOfWork(database.session_factory) as uow:
            from matter_context.domain import Matter
            uow.matters.add(Matter("rollback", "Not durable"))
            raise RuntimeError("fail")
    with SqlAlchemyUnitOfWork(database.session_factory) as uow:
        assert uow.matters.get("rollback") is None


def test_derived_records_round_trip(service) -> None:
    app, database = service
    matter = app.create_matter("Matter")
    source = app.append_narrative(matter.identifier, "Source text")
    claim = app.propose_claim(matter.identifier, "A proposed statement", "fact", Provenance.AI_ORGANIZED, source_id=source.identifier)
    block = ContentBlock("block", source.identifier, 0, "Source text", "characters:0-11")
    running = ProcessingRun.start("run", matter.identifier, "organize", (source.identifier,), provider="provider", model="model")
    run = running.succeed()
    brief = CaseBriefVersion("brief", matter.identifier, (source.identifier,), (claim.identifier,), (), "v1", "{}", "Brief")
    with SqlAlchemyUnitOfWork(database.session_factory) as uow:
        uow.content_blocks.add(block)
        uow.processing_runs.start(running)
        uow.case_briefs.add(brief)
        uow.commit()
    with SqlAlchemyUnitOfWork(database.session_factory) as uow:
        uow.processing_runs.finish(run)
        uow.commit()
    database.engine.dispose()
    reopened = Database.from_url(str(database.engine.url))
    with SqlAlchemyUnitOfWork(reopened.session_factory) as uow:
        assert uow.content_blocks.list_for_source(source.identifier) == [block]
        assert uow.processing_runs.get("run") == run
        assert uow.case_briefs.get("brief") == brief


def test_processing_run_repository_rejects_missing_and_non_running_transition_targets(service) -> None:
    app, database = service
    matter = app.create_matter("Matter")
    source = app.append_narrative(matter.identifier, "Source text")
    running = ProcessingRun.start("run", matter.identifier, "organize", (source.identifier,))
    succeeded = running.succeed()

    with pytest.raises(ProcessingRunTransitionError):
        with SqlAlchemyUnitOfWork(database.session_factory) as uow:
            uow.processing_runs.finish(succeeded)
            uow.commit()
    with SqlAlchemyUnitOfWork(database.session_factory) as uow:
        uow.processing_runs.start(running)
        uow.commit()
    with SqlAlchemyUnitOfWork(database.session_factory) as uow:
        uow.processing_runs.finish(succeeded)
        uow.commit()
    with pytest.raises(ProcessingRunTransitionError):
        with SqlAlchemyUnitOfWork(database.session_factory) as uow:
            uow.processing_runs.finish(running.fail("late failure"))
            uow.commit()
    with SqlAlchemyUnitOfWork(database.session_factory) as uow:
        persisted = uow.processing_runs.get(running.identifier)
    assert persisted == succeeded


def test_legacy_document_file_registration_preserves_failure_after_successful_cleanup(service, tmp_path, monkeypatch) -> None:
    app, _ = service
    original = tmp_path / "evidence.txt"
    original.write_text("evidence", encoding="utf-8")
    attachments = AttachmentStore(tmp_path / "attachments")
    cleanup_attempts: list[str] = []
    original_delete = attachments.delete

    def fail_registration(*_args, **_kwargs):
        raise RuntimeError("registration failed")

    def record_successful_cleanup(relative_path: str) -> None:
        cleanup_attempts.append(relative_path)
        original_delete(relative_path)

    monkeypatch.setattr(app, "register_document", fail_registration)
    monkeypatch.setattr(attachments, "delete", record_successful_cleanup)

    with pytest.raises(RuntimeError, match="registration failed") as error:
        app.register_document_file(
            "missing-matter", str(original), attachments,
            original_filename="evidence.txt", media_type="text/plain",
        )

    assert cleanup_attempts
    assert getattr(error.value, "__notes__", None) is None
    assert not list(attachments.root.rglob("*"))


def test_legacy_document_file_registration_preserves_failure_after_failed_cleanup(service, tmp_path, monkeypatch) -> None:
    app, _ = service
    original = tmp_path / "evidence.txt"
    original.write_text("evidence", encoding="utf-8")
    attachments = AttachmentStore(tmp_path / "attachments")
    cleanup_attempts: list[str] = []

    def fail_registration(*_args, **_kwargs):
        raise RuntimeError("registration failed")

    def fail_cleanup(relative_path: str) -> None:
        cleanup_attempts.append(relative_path)
        raise RuntimeError("cleanup failed")

    monkeypatch.setattr(app, "register_document", fail_registration)
    monkeypatch.setattr(attachments, "delete", fail_cleanup)

    with pytest.raises(RuntimeError, match="registration failed") as error:
        app.register_document_file(
            "missing-matter", str(original), attachments,
            original_filename="evidence.txt", media_type="text/plain",
        )

    assert cleanup_attempts
    assert error.value.__notes__ == ["Managed attachment cleanup also failed."]
    assert list(attachments.root.rglob("*"))
