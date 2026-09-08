"""Source-provider error taxonomy.

Categories follow DATA_INGESTION_BLUEPRINT.md section 7.1 and the
milestone error taxonomy. Every error declares whether it is
``retryable`` so the ingestion engine applies bounded retries only to
transient failures (network, 5xx, rate limit) and never to permanent
failures (auth, not-found, malformed responses).
"""

from __future__ import annotations

from src.core.errors import FinanceAIError

# Machine-readable categories (milestone error taxonomy, section 24).
CATEGORY_CONFIGURATION = "CONFIGURATION_ERROR"
CATEGORY_CONNECTION = "SOURCE_CONNECTION_ERROR"
CATEGORY_RATE_LIMIT = "SOURCE_RATE_LIMIT"
CATEGORY_RESPONSE = "SOURCE_RESPONSE_ERROR"
CATEGORY_NOT_FOUND = "SOURCE_NOT_FOUND"
CATEGORY_NORMALIZATION = "NORMALIZATION_ERROR"
CATEGORY_VALIDATION = "VALIDATION_ERROR"
CATEGORY_STORAGE = "DATABASE_ERROR"  # file-storage layer in the file-based MVP
CATEGORY_DUPLICATE = "DUPLICATE_DATA"  # stored rows conflict with fetched data
CATEGORY_EMPTY = "EMPTY_DATA"
CATEGORY_UNKNOWN = "UNKNOWN_ERROR"


class SourceError(FinanceAIError):
    """Base class for all source-provider failures."""

    category = CATEGORY_UNKNOWN
    retryable = False

    def __init__(
        self,
        message: str,
        *,
        retry_after_s: float | None = None,
        context: dict | None = None,
    ) -> None:
        super().__init__(message, context=context)
        self.retry_after_s = retry_after_s


class SourceConnectionError(SourceError):
    """Transient network failure: timeout, connection refused, DNS."""

    category = CATEGORY_CONNECTION
    retryable = True


class SourceRateLimitError(SourceError):
    """HTTP 429 — the provider asked us to slow down."""

    category = CATEGORY_RATE_LIMIT
    retryable = True


class SourceServerError(SourceError):
    """HTTP 5xx — transient provider failure."""

    category = CATEGORY_RESPONSE
    retryable = True


class SourceResponseError(SourceError):
    """Malformed/unexpected provider response (non-retryable)."""

    category = CATEGORY_RESPONSE
    retryable = False


class SourceNotFoundError(SourceError):
    """Ticker/range not found (HTTP 404) — permanent."""

    category = CATEGORY_NOT_FOUND
    retryable = False
