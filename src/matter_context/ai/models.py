"""Pydantic contracts shared by the application and provider adapters."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class GenerationUsage(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)

    def model_post_init(self, __context: Any, /) -> None:
        if (
            self.total_tokens is not None
            and self.input_tokens is not None
            and self.output_tokens is not None
            and self.total_tokens != self.input_tokens + self.output_tokens
        ):
            raise ValueError("total_tokens must equal input_tokens plus output_tokens")


class StructuredGenerationRequest(BaseModel):
    """Explicit selected-source input; provider adapters never receive domain objects."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    workflow_version: str = Field(min_length=1, max_length=128)
    source_ids: tuple[str, ...] = Field(min_length=1)
    content: str = Field(min_length=1)
    instruction: str = Field(min_length=1)
    output_schema: dict[str, Any]

    @field_validator("source_ids")
    @classmethod
    def unique_source_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise ValueError("source_ids must be unique")
        return value


class StructuredGenerationResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    provider: str = Field(min_length=1, max_length=255)
    model: str = Field(min_length=1, max_length=255)
    output: dict[str, Any]
    usage: GenerationUsage | None = None
