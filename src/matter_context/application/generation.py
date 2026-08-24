"""Explicit selected-source structured-generation workflow."""

from __future__ import annotations

from dataclasses import dataclass, replace
from time import monotonic
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from matter_context.ai import (
    FakeStructuredGenerationProvider,
    ProviderError,
    StructuredGenerationProvider,
    StructuredGenerationRequest,
)
from matter_context.domain import ProcessingRun, ProcessingStatus, utcnow

from .persistence import UnitOfWorkFactory

ORGANIZED_UPDATE_WORKFLOW_VERSION = "organized-update/v1"
_INSTRUCTION = (
    "Organize only the supplied source. Return JSON matching the schema. Do not decide facts, "
    "confirm reviews, or claim that omitted information exists."
)


class OrganizedUpdate(BaseModel):
    """Versioned, display-only output; it has no domain write authority."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    workflow_version: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    key_points: tuple[str, ...] = Field(default=())
    open_questions: tuple[str, ...] = Field(default=())
    source_ids: tuple[str, ...] = Field(min_length=1)

    @field_validator("workflow_version")
    @classmethod
    def matching_workflow(cls, value: str) -> str:
        if value != ORGANIZED_UPDATE_WORKFLOW_VERSION:
            raise ValueError("workflow_version is unsupported")
        return value


@dataclass(frozen=True, slots=True)
class OrganizedUpdateResult:
    run: ProcessingRun
    update: OrganizedUpdate


class StructuredGenerationService:
    """Persists audit metadata only; sources, claims, reviews, and briefs stay immutable."""

    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        provider: StructuredGenerationProvider | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._provider = provider or FakeStructuredGenerationProvider()

    def organize_selected_source(
        self, matter_id: str, source_id: str
    ) -> OrganizedUpdateResult:
        with self._uow_factory() as uow:
            source = uow.sources.get(source_id)
            if source is None or source.matter_id != matter_id:
                raise ValueError("The selected source does not belong to this case.")
            content = source.text
            if content is None:
                content = "\n\n".join(
                    block.text
                    for block in uow.content_blocks.list_for_source(source_id)
                )
            if not content or not content.strip():
                raise ValueError(
                    "The selected source has no extracted text to organize."
                )
            run = ProcessingRun(
                identifier=str(uuid4()),
                matter_id=matter_id,
                operation="organize_selected_source",
                input_source_ids=(source_id,),
                status=ProcessingStatus.RUNNING,
                provider=self._provider_name(),
                model=self._model_name(),
                workflow_version=ORGANIZED_UPDATE_WORKFLOW_VERSION,
            )
            uow.processing_runs.add(run)
            uow.commit()

        started = monotonic()
        request = StructuredGenerationRequest(
            workflow_version=ORGANIZED_UPDATE_WORKFLOW_VERSION,
            source_ids=(source_id,),
            content=content,
            instruction=_INSTRUCTION,
            output_schema=OrganizedUpdate.model_json_schema(),
        )
        try:
            response = self._provider.generate(request)
            update = OrganizedUpdate.model_validate(response.output)
            if update.source_ids != (source_id,):
                raise ValueError("Structured output referenced an unselected source.")
        except ProviderError as error:
            self._finish(
                run,
                ProcessingStatus.FAILED,
                provider=self._provider_name(),
                model=self._model_name(),
                error_summary=str(error),
                duration_ms=_duration_ms(started),
            )
            raise
        except ValueError as error:
            from matter_context.ai import ProviderResponseValidationError

            failure = ProviderResponseValidationError()
            self._finish(
                run,
                ProcessingStatus.FAILED,
                provider=self._provider_name(),
                model=self._model_name(),
                error_summary=str(failure),
                duration_ms=_duration_ms(started),
            )
            raise failure from error
        completed = self._finish(
            run,
            ProcessingStatus.SUCCEEDED,
            provider=response.provider,
            model=response.model,
            usage=response.usage,
            duration_ms=_duration_ms(started),
        )
        return OrganizedUpdateResult(completed, update)

    def _provider_name(self) -> str:
        return str(
            getattr(self._provider, "provider_name", type(self._provider).__name__)
        )

    def _model_name(self) -> str:
        return str(getattr(self._provider, "model_name", "unknown"))

    def check_connection(self) -> None:
        """Exercise the configured provider with fixed synthetic content only."""
        request = StructuredGenerationRequest(
            workflow_version=ORGANIZED_UPDATE_WORKFLOW_VERSION,
            source_ids=("connection-check",),
            content="Synthetic connection check. This is not matter content.",
            instruction=_INSTRUCTION,
            output_schema=OrganizedUpdate.model_json_schema(),
        )
        try:
            response = self._provider.generate(request)
            update = OrganizedUpdate.model_validate(response.output)
            if update.source_ids != ("connection-check",):
                raise ValueError("Structured output referenced a non-synthetic source.")
        except ProviderError:
            raise
        except (TypeError, ValueError) as error:
            from matter_context.ai import ProviderResponseValidationError

            raise ProviderResponseValidationError() from error

    def _finish(
        self,
        run: ProcessingRun,
        status: ProcessingStatus,
        *,
        provider: str | None = None,
        model: str | None = None,
        usage: object | None = None,
        error_summary: str | None = None,
        duration_ms: int,
    ) -> ProcessingRun:
        values = {"input_tokens": None, "output_tokens": None, "total_tokens": None}
        if usage is not None:
            values = {
                "input_tokens": usage.input_tokens,
                "output_tokens": usage.output_tokens,
                "total_tokens": usage.total_tokens,
            }
        completed = replace(
            run,
            status=status,
            provider=provider or run.provider,
            model=model or run.model,
            completed_at=utcnow(),
            error_summary=error_summary,
            duration_ms=duration_ms,
            usage_input_tokens=values["input_tokens"],
            usage_output_tokens=values["output_tokens"],
            usage_total_tokens=values["total_tokens"],
        )
        with self._uow_factory() as uow:
            uow.processing_runs.update(completed)
            uow.commit()
        return completed


def _duration_ms(started: float) -> int:
    return max(0, round((monotonic() - started) * 1000))
