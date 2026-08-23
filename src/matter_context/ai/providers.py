"""Small configurable OpenAI-compatible adapter and deterministic offline fake."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from typing import Any, Protocol

import httpx

from .errors import (
    ProviderConfigurationError,
    ProviderConnectionError,
    ProviderError,
    ProviderRateLimitError,
    ProviderRefusalError,
    ProviderResponseValidationError,
    ProviderServerError,
    ProviderTimeoutError,
)
from .models import (
    GenerationUsage,
    StructuredGenerationRequest,
    StructuredGenerationResult,
)


class StructuredGenerationProvider(Protocol):
    provider_name: str
    model_name: str

    def generate(
        self, request: StructuredGenerationRequest
    ) -> StructuredGenerationResult: ...


class FakeStructuredGenerationProvider:
    """No-network provider with stable output for development and tests."""

    provider_name = "fake"
    model_name = "deterministic-v1"

    def generate(
        self, request: StructuredGenerationRequest
    ) -> StructuredGenerationResult:
        excerpt = " ".join(request.content.split())
        output = {
            "workflow_version": request.workflow_version,
            "summary": excerpt[:400] or "No source text was supplied.",
            "key_points": [excerpt[:160] or "No source text was supplied."],
            "open_questions": [],
            "source_ids": list(request.source_ids),
        }
        usage = GenerationUsage(
            input_tokens=len(request.content.split()),
            output_tokens=16,
            total_tokens=len(request.content.split()) + 16,
        )
        return StructuredGenerationResult(
            provider=self.provider_name,
            model=self.model_name,
            output=output,
            usage=usage,
        )


class OpenAICompatibleProvider:
    """JSON-only adapter for owner-configured OpenAI-compatible chat endpoints."""

    provider_name = "openai-compatible"

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: float = 30.0,
        max_retries: int = 2,
        client: httpx.Client | None = None,
    ) -> None:
        if not base_url.strip() or not api_key.strip() or not model.strip():
            raise ProviderConfigurationError()
        if timeout_seconds <= 0 or max_retries < 0:
            raise ProviderConfigurationError(
                "Model timeout and retry limits must be valid.", secret=api_key
            )
        self.base_url = base_url.rstrip("/")
        self._api_key = api_key
        self.model = model
        self.model_name = model
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self._client = client or httpx.Client(timeout=timeout_seconds)

    def generate(
        self, request: StructuredGenerationRequest
    ) -> StructuredGenerationResult:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": request.instruction},
                {"role": "user", "content": request.content},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "structured_generation",
                    "strict": True,
                    "schema": request.output_schema,
                },
            },
        }
        for attempt in range(self.max_retries + 1):
            try:
                response = self._client.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    timeout=self.timeout_seconds,
                )
            except httpx.TimeoutException:
                failure: ProviderError = ProviderTimeoutError(secret=self._api_key)
            except httpx.NetworkError:
                failure = ProviderConnectionError(secret=self._api_key)
            except httpx.HTTPError:
                failure = ProviderConnectionError(secret=self._api_key)
            else:
                if response.status_code == 429:
                    failure = ProviderRateLimitError(secret=self._api_key)
                elif 500 <= response.status_code <= 599:
                    failure = ProviderServerError(secret=self._api_key)
                elif response.is_error:
                    raise ProviderConnectionError(
                        f"Model service returned HTTP {response.status_code}.",
                        secret=self._api_key,
                    )
                else:
                    return self._parse_response(response)
            if attempt == self.max_retries or not isinstance(
                failure,
                (
                    ProviderTimeoutError,
                    ProviderRateLimitError,
                    ProviderServerError,
                    ProviderConnectionError,
                ),
            ):
                raise failure
        raise AssertionError("unreachable")

    def _parse_response(self, response: httpx.Response) -> StructuredGenerationResult:
        try:
            body = response.json()
            choice = body["choices"][0]
            message = choice["message"]
            if (
                message.get("refusal")
                or choice.get("finish_reason") == "content_filter"
            ):
                raise ProviderRefusalError()
            content = message["content"]
            if not isinstance(content, str):
                raise TypeError("content is not a string")
            output = json.loads(content)
            if not isinstance(output, dict):
                raise TypeError("content is not an object")
            usage_data: Mapping[str, Any] = body.get("usage") or {}
            usage = (
                GenerationUsage(
                    input_tokens=usage_data.get("prompt_tokens"),
                    output_tokens=usage_data.get("completion_tokens"),
                    total_tokens=usage_data.get("total_tokens"),
                )
                if usage_data
                else None
            )
        except ProviderRefusalError:
            raise
        except (AttributeError, IndexError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise ProviderResponseValidationError() from error
        return StructuredGenerationResult(
            provider=self.provider_name,
            model=self.model_name,
            output=output,
            usage=usage,
        )


def provider_from_environment(
    environment: Mapping[str, str] | None = None,
) -> StructuredGenerationProvider:
    """Use the fake only when all owner configuration fields are blank."""
    values = os.environ if environment is None else environment
    base_url = values.get("MATTER_CONTEXT_MODEL_BASE_URL", "").strip()
    api_key = values.get("MATTER_CONTEXT_MODEL_API_KEY", "").strip()
    model = values.get("MATTER_CONTEXT_MODEL_NAME", "").strip()
    if not any((base_url, api_key, model)):
        return FakeStructuredGenerationProvider()
    if not all((base_url, api_key, model)):
        raise ProviderConfigurationError()
    try:
        timeout = float(values.get("MATTER_CONTEXT_MODEL_TIMEOUT_SECONDS", "30"))
        retries = int(values.get("MATTER_CONTEXT_MODEL_MAX_RETRIES", "2"))
    except ValueError as error:
        raise ProviderConfigurationError(
            "Model timeout and retry limits must be numeric.", secret=api_key
        ) from error
    return OpenAICompatibleProvider(
        base_url=base_url,
        api_key=api_key,
        model=model,
        timeout_seconds=timeout,
        max_retries=retries,
    )
