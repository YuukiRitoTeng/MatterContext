from __future__ import annotations

import json

import httpx
import pytest

from matter_context.ai import (
    FakeStructuredGenerationProvider,
    OpenAICompatibleProvider,
    ProviderRateLimitError,
    ProviderRefusalError,
    ProviderResponseValidationError,
    ProviderServerError,
    ProviderTimeoutError,
    StructuredGenerationRequest,
    StructuredGenerationResult,
    provider_from_environment,
)
from matter_context.application.generation import StructuredGenerationService
from matter_context.application.matters import MatterService
from matter_context.domain import ProcessingStatus
from matter_context.execution.tasks import (
    CancellationToken,
    StructuredGenerationTask,
    TaskFailure,
)
from matter_context.storage.database import Database, upgrade_database
from matter_context.storage.unit_of_work import SqlAlchemyUnitOfWork


def _request() -> StructuredGenerationRequest:
    return StructuredGenerationRequest(
        workflow_version="organized-update/v1",
        source_ids=("source",),
        content="Selected source text.",
        instruction="Return JSON.",
        output_schema={"type": "object"},
    )


def _response(
    output: dict[str, object], *, usage: dict[str, int] | None = None
) -> httpx.Response:
    body: dict[str, object] = {
        "choices": [{"message": {"content": json.dumps(output)}}]
    }
    if usage is not None:
        body["usage"] = usage
    return httpx.Response(200, json=body)


def _provider(handler, *, retries: int = 0) -> OpenAICompatibleProvider:
    return OpenAICompatibleProvider(
        base_url="http://model.test/api",
        api_key="test-secret",
        model="test-model",
        max_retries=retries,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def test_compatible_adapter_uses_configured_endpoint_model_schema_and_usage() -> None:
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return _response(
            {"ok": True},
            usage={"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
        )

    result = _provider(handler).generate(_request())

    assert str(seen[0].url) == "http://model.test/api/chat/completions"
    assert json.loads(seen[0].content)["model"] == "test-model"
    assert "test-secret" not in repr(result)
    assert result.usage and result.usage.total_tokens == 5


@pytest.mark.parametrize(
    ("response", "error"),
    [
        (httpx.Response(429), ProviderRateLimitError),
        (httpx.Response(503), ProviderServerError),
        (
            httpx.Response(200, json={"choices": [{"message": {"refusal": "No"}}]}),
            ProviderRefusalError,
        ),
        (
            httpx.Response(
                200, json={"choices": [{"message": {"content": "not-json"}}]}
            ),
            ProviderResponseValidationError,
        ),
    ],
)
def test_compatible_adapter_maps_sanitized_typed_failures(
    response: httpx.Response, error: type[Exception]
) -> None:
    with pytest.raises(error) as raised:
        _provider(lambda _: response).generate(_request())
    assert "test-secret" not in str(raised.value)


def test_compatible_adapter_maps_empty_choices_to_response_validation_error() -> None:
    with pytest.raises(ProviderResponseValidationError):
        _provider(lambda _: httpx.Response(200, json={"choices": []})).generate(_request())


def test_compatible_adapter_retries_and_maps_timeouts() -> None:
    attempts = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return _response({"ok": True}) if attempts == 2 else httpx.Response(503)

    assert _provider(handler, retries=1).generate(_request()).output == {"ok": True}
    assert attempts == 2

    class TimeoutClient:
        def post(self, *args, **kwargs):
            raise httpx.ReadTimeout("test-secret")

    with pytest.raises(ProviderTimeoutError) as raised:
        OpenAICompatibleProvider(
            base_url="http://model.test",
            api_key="test-secret",
            model="m",
            max_retries=0,
            client=TimeoutClient(),
        ).generate(_request())
    assert "test-secret" not in str(raised.value)


def test_fake_generation_runs_in_background_and_persists_only_a_processing_audit(
    tmp_path,
) -> None:
    database = Database.from_url(f"sqlite:///{tmp_path / 'generated.sqlite3'}")
    upgrade_database(str(database.engine.url))
    factory = lambda: SqlAlchemyUnitOfWork(database.session_factory)
    matter_service = MatterService(factory)
    matter = matter_service.create_matter("Generation")
    source = matter_service.append_narrative(
        matter.identifier, "The client reports a missed payment."
    )
    task = StructuredGenerationTask(
        StructuredGenerationService(factory, FakeStructuredGenerationProvider()),
        matter.identifier,
        source.identifier,
    )

    result = task.run(CancellationToken(), lambda _: None)

    assert result.summary == "The client reports a missed payment."
    with factory() as uow:
        run = uow.processing_runs.get(result.run_id)
        assert uow.sources.get(source.identifier) == source
        assert uow.claims.list_for_matter(matter.identifier) == []
        assert (
            run
            and run.status is ProcessingStatus.SUCCEEDED
            and run.input_source_ids == (source.identifier,)
        )
        assert (
            run.usage_total_tokens == run.usage_input_tokens + run.usage_output_tokens
        )


def test_invalid_fake_output_fails_audit_and_exposes_only_actionable_task_message(
    tmp_path,
) -> None:
    class InvalidProvider:
        provider_name = "invalid-fake"
        model_name = "invalid-model"

        def generate(self, request):
            return StructuredGenerationResult(
                provider="fake", model="broken", output={"summary": "missing schema"}
            )

    database = Database.from_url(f"sqlite:///{tmp_path / 'invalid.sqlite3'}")
    upgrade_database(str(database.engine.url))
    factory = lambda: SqlAlchemyUnitOfWork(database.session_factory)
    matter = MatterService(factory).create_matter("Invalid")
    source = MatterService(factory).append_narrative(matter.identifier, "source")
    service = StructuredGenerationService(factory, InvalidProvider())

    with pytest.raises(TaskFailure, match="invalid structured response"):
        StructuredGenerationTask(service, matter.identifier, source.identifier).run(
            CancellationToken(), lambda _: None
        )
    with factory() as uow:
        run = uow.processing_runs.latest_for_source(source.identifier)
        assert run and run.status is ProcessingStatus.FAILED
        assert (run.provider, run.model) == ("invalid-fake", "invalid-model")


def test_malformed_adapter_response_finishes_audit_with_failure_metadata(tmp_path) -> None:
    database = Database.from_url(f"sqlite:///{tmp_path / 'malformed.sqlite3'}")
    upgrade_database(str(database.engine.url))
    factory = lambda: SqlAlchemyUnitOfWork(database.session_factory)
    matter = MatterService(factory).create_matter("Malformed")
    source = MatterService(factory).append_narrative(matter.identifier, "source")
    provider = _provider(lambda _: httpx.Response(200, json={"choices": []}))

    with pytest.raises(TaskFailure, match="invalid structured response"):
        StructuredGenerationTask(StructuredGenerationService(factory, provider), matter.identifier, source.identifier).run(CancellationToken(), lambda _: None)
    with factory() as uow:
        run = uow.processing_runs.latest_for_source(source.identifier)
    assert run and run.status is ProcessingStatus.FAILED
    assert run.completed_at is not None and run.duration_ms is not None
    assert (run.provider, run.model, run.workflow_version) == ("openai-compatible", "test-model", "organized-update/v1")
    assert run.input_source_ids == (source.identifier,)
    assert run.error_summary == "The model service returned an invalid structured response."


def test_connection_check_uses_only_fixed_synthetic_payload() -> None:
    class RecordingProvider(FakeStructuredGenerationProvider):
        def __init__(self) -> None:
            self.requests = []

        def generate(self, request):
            self.requests.append(request)
            return super().generate(request)

    provider = RecordingProvider()
    StructuredGenerationService(lambda: None, provider).check_connection()

    assert len(provider.requests) == 1
    assert provider.requests[0].source_ids == ("connection-check",)
    assert (
        provider.requests[0].content
        == "Synthetic connection check. This is not matter content."
    )


def test_empty_environment_isolated_and_connection_schema_failures_are_typed() -> None:
    assert isinstance(provider_from_environment({}), FakeStructuredGenerationProvider)

    class InvalidConnectionProvider:
        provider_name = "invalid"
        model_name = "invalid"

        def generate(self, request):
            return StructuredGenerationResult(provider="invalid", model="invalid", output={"summary": "missing fields"})

    with pytest.raises(ProviderResponseValidationError):
        StructuredGenerationService(lambda: None, InvalidConnectionProvider()).check_connection()


def test_secret_redaction_covers_task_failure_sqlite_and_diagnostics(tmp_path) -> None:
    secret = "sqlite-secret"
    database = Database.from_url(f"sqlite:///{tmp_path / 'redaction.sqlite3'}")
    upgrade_database(str(database.engine.url))
    factory = lambda: SqlAlchemyUnitOfWork(database.session_factory)
    matter = MatterService(factory).create_matter("Redaction")
    source = MatterService(factory).append_narrative(matter.identifier, "source")
    provider = OpenAICompatibleProvider(
        base_url="http://model.test",
        api_key=secret,
        model="redaction-model",
        max_retries=0,
        client=httpx.Client(
            transport=httpx.MockTransport(lambda _: httpx.Response(503))
        ),
    )
    task = StructuredGenerationTask(
        StructuredGenerationService(factory, provider),
        matter.identifier,
        source.identifier,
    )

    with pytest.raises(TaskFailure) as failure:
        task.run(CancellationToken(), lambda _: None)
    assert secret not in str(failure.value)
    with factory() as uow:
        run = uow.processing_runs.latest_for_source(source.identifier)
        assert (
            run
            and run.provider == "openai-compatible"
            and run.model == "redaction-model"
        )
        assert secret not in (run.error_summary or "")
    assert secret.encode() not in (tmp_path / "redaction.sqlite3").read_bytes()
    diagnostics = tmp_path / "diagnostics"
    assert not diagnostics.exists() or all(
        secret.encode() not in path.read_bytes()
        for path in diagnostics.rglob("*")
        if path.is_file()
    )
