"""OpenAI-compatible error response for /v1/* endpoints.

Maps UniAPI error codes to OpenAI's standard error format
(https://platform.openai.com/docs/guides/error-codes/api-errors)
so that OpenAI-compatible clients (Claude Code, OpenWebUI,
LobeChat, etc.) correctly interpret errors.
"""

from __future__ import annotations

from typing import Any

# ── Mapping: UniAPI error code → (http_status, openai_type, openai_code) ──

OPENAI_ERROR_MAP: dict[str, tuple[int, str, str]] = {
    # Authentication
    "UNIAPI_INVALID_TOKEN":           (401, "authentication_error",  "invalid_api_key"),
    "UNIAPI_TOKEN_EXPIRED":           (401, "authentication_error",  "invalid_api_key"),
    # Authorization
    "UNIAPI_TOKEN_MODEL_NOT_ALLOWED": (404, "invalid_request_error", "model_not_found"),
    "UNIAPI_ADMIN_REQUIRED":          (403, "authorization_error",   "permission_denied"),
    "UNIAPI_GROUP_ACCESS_DENIED":     (403, "authorization_error",   "permission_denied"),
    # Validation / Request errors
    "UNIAPI_INVALID_REQUEST":         (400, "invalid_request_error", "invalid_request_error"),
    "UNIAPI_MODEL_NOT_SPECIFIED":     (400, "invalid_request_error", "model_not_found"),
    "UNIAPI_MODEL_NOT_SUPPORTED":     (404, "invalid_request_error", "model_not_found"),
    "UNIAPI_RESOURCE_NOT_FOUND":      (404, "not_found_error",       "resource_not_found"),
    # Quota
    "UNIAPI_QUOTA_EXHAUSTED":         (429, "insufficient_quota",    "insufficient_quota"),
    # Rate limit
    "UNIAPI_RATE_LIMITED":            (429, "rate_limit_error",      "rate_limit_exceeded"),
    # Service availability
    "UNIAPI_SERVICE_DISABLED":        (503, "api_error",             "server_error"),
    "UNIAPI_CHANNEL_UNAVAILABLE":     (503, "api_error",             "server_error"),
    # Upstream
    "UPSTREAM_TIMEOUT":               (504, "api_error",             "upstream_error"),
    "UPSTREAM_UNAVAILABLE":           (503, "api_error",             "upstream_error"),
    "UPSTREAM_BAD_RESPONSE":          (502, "api_error",             "upstream_error"),
    "UPSTREAM_RATE_LIMITED":          (429, "rate_limit_error",      "upstream_error"),
    "UPSTREAM_CONNECTION_FAILED":     (502, "api_error",             "upstream_error"),
}

# Default fallback for unknown codes
_DEFAULT_MAP: tuple[int, str, str] = (500, "api_error", "server_error")


def get_openai_error_meta(code: str) -> tuple[int, str, str]:
    """Return (http_status, openai_type, openai_code) for a UniAPI error code.

    Parameters
    ----------
    code : str
        A UniAPI error code (e.g. ``UNIAPI_TOKEN_MODEL_NOT_ALLOWED``).

    Returns
    -------
    tuple[int, str, str]
        HTTP status code, OpenAI error type string, OpenAI error code string.
        Unknown codes return (500, "api_error", "server_error").
    """
    return OPENAI_ERROR_MAP.get(code, _DEFAULT_MAP)


def build_openai_error_response(
    message: str,
    *,
    openai_type: str = "invalid_request_error",
    openai_code: str = "server_error",
    param: str | None = None,
) -> dict[str, dict[str, str | None]]:
    """Build an OpenAI-compatible error response dict.

    Parameters
    ----------
    message : str
        Human-readable error description.
    openai_type : str
        OpenAI error type (e.g. ``invalid_request_error``).
    openai_code : str
        OpenAI error code (e.g. ``model_not_found``).
    param : str or None
        Parameter that caused the error, or None.

    Returns
    -------
    dict
        OpenAI-format error response:
        ``{"error": {"message": ..., "type": ..., "param": ..., "code": ...}}``
    """
    return {
        "error": {
            "message": message,
            "type": openai_type,
            "param": param,
            "code": openai_code,
        }
    }
