"""Provider-neutral structured generation boundary."""

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
from .providers import (
    FakeStructuredGenerationProvider,
    OpenAICompatibleProvider,
    StructuredGenerationProvider,
    provider_from_environment,
)

__all__ = [
    "FakeStructuredGenerationProvider",
    "GenerationUsage",
    "OpenAICompatibleProvider",
    "ProviderConfigurationError",
    "ProviderConnectionError",
    "ProviderError",
    "ProviderRateLimitError",
    "ProviderRefusalError",
    "ProviderResponseValidationError",
    "ProviderServerError",
    "ProviderTimeoutError",
    "StructuredGenerationProvider",
    "StructuredGenerationRequest",
    "StructuredGenerationResult",
    "provider_from_environment",
]
