"""Typed, credential-safe provider failures."""

from __future__ import annotations

import re


def redact_credentials(value: str, *secrets: str | None) -> str:
    """Remove bearer credentials and configured secrets from support-facing text."""
    redacted = re.sub(
        r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s,;]+", r"\1[REDACTED]", value
    )
    redacted = re.sub(
        r"(?i)(api[_ -]?key\s*[:=]\s*)[^\s,;]+", r"\1[REDACTED]", redacted
    )
    for secret in secrets:
        if secret:
            redacted = redacted.replace(secret, "[REDACTED]")
    return redacted


class ProviderError(Exception):
    """A safe provider failure suitable for application and desktop boundaries."""

    message = "The model service could not complete the request."

    def __init__(self, detail: str | None = None, *, secret: str | None = None) -> None:
        self.detail = redact_credentials(detail or self.message, secret)
        super().__init__(self.detail)


class ProviderConfigurationError(ProviderError):
    message = "Model connection configuration is incomplete."


class ProviderConnectionError(ProviderError):
    message = "The model service could not be reached."


class ProviderTimeoutError(ProviderError):
    message = "The model service timed out. Try again later."


class ProviderRateLimitError(ProviderError):
    message = "The model service is temporarily rate limited. Try again later."


class ProviderServerError(ProviderError):
    message = "The model service reported a temporary server error. Try again later."


class ProviderRefusalError(ProviderError):
    message = "The model service declined this request."


class ProviderResponseValidationError(ProviderError):
    message = "The model service returned an invalid structured response."
