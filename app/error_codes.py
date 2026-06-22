"""UniAPI standardized error codes.

Defines the canonical error code constants, error types, and the
code → (http_status, error_type) mapping table used by the unified
error response system.

See: docs/error-codes/UNIAPI_ERROR_CODE_SPEC_DRAFT.md
"""

from __future__ import annotations

from typing import Tuple

# ── Error code constants ─────────────────────────────────────────────────────

# Authentication & authorization
UNIAPI_INVALID_TOKEN = "UNIAPI_INVALID_TOKEN"
UNIAPI_TOKEN_EXPIRED = "UNIAPI_TOKEN_EXPIRED"
UNIAPI_TOKEN_MODEL_NOT_ALLOWED = "UNIAPI_TOKEN_MODEL_NOT_ALLOWED"
UNIAPI_ADMIN_REQUIRED = "UNIAPI_ADMIN_REQUIRED"
UNIAPI_GROUP_ACCESS_DENIED = "UNIAPI_GROUP_ACCESS_DENIED"

# Request & validation
UNIAPI_INVALID_REQUEST = "UNIAPI_INVALID_REQUEST"
UNIAPI_MODEL_NOT_SPECIFIED = "UNIAPI_MODEL_NOT_SPECIFIED"
UNIAPI_MODEL_NOT_SUPPORTED = "UNIAPI_MODEL_NOT_SUPPORTED"
UNIAPI_UNSUPPORTED_PARAMETER = "UNIAPI_UNSUPPORTED_PARAMETER"
UNIAPI_RESOURCE_NOT_FOUND = "UNIAPI_RESOURCE_NOT_FOUND"

# Quota & rate limiting
UNIAPI_QUOTA_EXHAUSTED = "UNIAPI_QUOTA_EXHAUSTED"
UNIAPI_RATE_LIMITED = "UNIAPI_RATE_LIMITED"

# Upstream
UPSTREAM_TIMEOUT = "UPSTREAM_TIMEOUT"
UPSTREAM_UNAVAILABLE = "UPSTREAM_UNAVAILABLE"
UPSTREAM_BAD_RESPONSE = "UPSTREAM_BAD_RESPONSE"
UPSTREAM_RATE_LIMITED = "UPSTREAM_RATE_LIMITED"
UPSTREAM_CONNECTION_FAILED = "UPSTREAM_CONNECTION_FAILED"

# Service availability
UNIAPI_SERVICE_DISABLED = "UNIAPI_SERVICE_DISABLED"
UNIAPI_CHANNEL_UNAVAILABLE = "UNIAPI_CHANNEL_UNAVAILABLE"

# Internal
UNIAPI_INTERNAL_ERROR = "UNIAPI_INTERNAL_ERROR"

# ── Error types ──────────────────────────────────────────────────────────────

class ErrorType:
    """Canonical error type labels (lower_snake_case)."""

    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    VALIDATION = "validation"
    QUOTA = "quota"
    RATE_LIMIT = "rate_limit"
    UPSTREAM = "upstream"
    INTERNAL = "internal"
    NOT_FOUND = "not_found"


# ── Code → (status_code, type) mapping ───────────────────────────────────────

ERROR_CODE_MAP: dict[str, Tuple[int, str]] = {
    # Authentication & authorization
    UNIAPI_INVALID_TOKEN: (401, ErrorType.AUTHENTICATION),
    UNIAPI_TOKEN_EXPIRED: (401, ErrorType.AUTHENTICATION),
    UNIAPI_TOKEN_MODEL_NOT_ALLOWED: (403, ErrorType.AUTHORIZATION),
    UNIAPI_ADMIN_REQUIRED: (403, ErrorType.AUTHORIZATION),
    UNIAPI_GROUP_ACCESS_DENIED: (403, ErrorType.AUTHORIZATION),
    # Request & validation
    UNIAPI_INVALID_REQUEST: (400, ErrorType.VALIDATION),
    UNIAPI_MODEL_NOT_SPECIFIED: (400, ErrorType.VALIDATION),
    UNIAPI_MODEL_NOT_SUPPORTED: (400, ErrorType.VALIDATION),
    UNIAPI_UNSUPPORTED_PARAMETER: (400, ErrorType.VALIDATION),
    UNIAPI_RESOURCE_NOT_FOUND: (404, ErrorType.NOT_FOUND),
    # Quota & rate limiting
    UNIAPI_QUOTA_EXHAUSTED: (402, ErrorType.QUOTA),
    UNIAPI_RATE_LIMITED: (429, ErrorType.RATE_LIMIT),
    # Upstream
    UPSTREAM_TIMEOUT: (504, ErrorType.UPSTREAM),
    UPSTREAM_UNAVAILABLE: (503, ErrorType.UPSTREAM),
    UPSTREAM_BAD_RESPONSE: (502, ErrorType.UPSTREAM),
    UPSTREAM_RATE_LIMITED: (429, ErrorType.UPSTREAM),
    UPSTREAM_CONNECTION_FAILED: (502, ErrorType.UPSTREAM),
    # Service availability
    UNIAPI_SERVICE_DISABLED: (503, ErrorType.INTERNAL),
    UNIAPI_CHANNEL_UNAVAILABLE: (503, ErrorType.UPSTREAM),
    # Internal
    UNIAPI_INTERNAL_ERROR: (500, ErrorType.INTERNAL),
}

# Default fallback for unknown codes
_FALLBACK = (500, ErrorType.INTERNAL)


def get_error_meta(code: str) -> Tuple[int, str]:
    """Return (status_code, type) for a given error code.

    Returns the default (500, "internal") for unrecognised codes.
    Provider-specific codes (PROVIDER_*) are mapped to 502/upstream.
    """
    if code in ERROR_CODE_MAP:
        return ERROR_CODE_MAP[code]

    # Handle dynamically-generated PROVIDER_* codes (e.g. PROVIDER_DEEPSEEK_SAFETY_BLOCKED)
    if code.startswith("PROVIDER_"):
        return (502, ErrorType.UPSTREAM)

    return _FALLBACK
