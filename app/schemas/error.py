"""UniAPI standardized error response schemas.

Defines the Pydantic models and factory functions for the unified
error response structure per spec §5.

See: docs/error-codes/UNIAPI_ERROR_CODE_SPEC_DRAFT.md
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field


# ── Upstream error detail ────────────────────────────────────────────────────


class UpstreamErrorDetail(BaseModel):
    """Structured upstream error info (spec §5.3).

    Note: there is NO ``raw`` field — raw upstream response bodies are
    logged server-side only, never returned to clients.
    """

    model_config = {"extra": "forbid"}

    provider: str = Field(..., description="Upstream provider name, e.g. 'deepseek'")
    status_code: int = Field(..., description="Upstream HTTP status code")
    code: Optional[str] = Field(None, description="Upstream original error code")
    message: Optional[str] = Field(None, description="Upstream original error message")
    request_id: Optional[str] = Field(None, description="Upstream request ID for trace correlation")


# ── Standard error detail ────────────────────────────────────────────────────


class StandardErrorDetail(BaseModel):
    """The canonical error object returned by all UniAPI endpoints (spec §5.1)."""

    code: str = Field(..., description="UniAPI error code — primary branch key for clients")
    message: str = Field(..., description="Human-readable error message")
    type: str = Field(..., description="Error category: authentication, authorization, validation, quota, rate_limit, upstream, internal, not_found")
    status_code: int = Field(..., description="HTTP status code mirror")
    details: Optional[dict[str, Any]] = Field(None, description="Structured context (dynamic parameters)")
    suggestion: Optional[str] = Field(None, description="Actionable fix suggestion")
    request_id: str = Field(
        default_factory=lambda: f"req_{uuid.uuid4().hex}",
        description="Trace ID from RequestIDMiddleware",
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        description="ISO 8601 UTC timestamp",
    )
    upstream: Optional[UpstreamErrorDetail] = Field(None, description="Upstream error detail (only when applicable)")


# ── Standard error response wrapper ──────────────────────────────────────────


class StandardErrorResponse(BaseModel):
    """Top-level error response envelope."""

    success: bool = Field(False, description="Always false for error responses")
    error: StandardErrorDetail


# ── Factory function ─────────────────────────────────────────────────────────


def build_error_response(
    code: str,
    message: str,
    *,
    details: Optional[dict[str, Any]] = None,
    suggestion: Optional[str] = None,
    request_id: Optional[str] = None,
    upstream: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Build a standard error response dict from an error code and message.

    Looks up status_code + type from ``ERROR_CODE_MAP``. Unknown codes
    fall back to 500 / "internal".

    Parameters
    ----------
    code : str
        UniAPI error code (e.g. ``UNIAPI_INVALID_TOKEN``).
    message : str
        Human-readable error message.
    details : dict, optional
        Structured context.
    suggestion : str, optional
        Actionable fix suggestion.
    request_id : str, optional
        Explicit request ID. Auto-generated when omitted.
    upstream : dict, optional
        Upstream error info. Converted to ``UpstreamErrorDetail``.

    Returns
    -------
    dict
        Ready-to-serialize error response with ``success=False``.
    """
    from app.error_codes import get_error_meta

    status_code, error_type = get_error_meta(code)

    upstream_obj = None
    if upstream is not None:
        upstream_obj = UpstreamErrorDetail(**upstream)

    error_detail = StandardErrorDetail(
        code=code,
        message=message,
        type=error_type,
        status_code=status_code,
        details=details,
        suggestion=suggestion,
        request_id=request_id or f"req_{uuid.uuid4().hex}",
        upstream=upstream_obj,
    )

    response = StandardErrorResponse(success=False, error=error_detail)
    return response.model_dump(exclude_none=True)


def build_compat_error_response(
    code: str,
    message: str,
    *,
    details: Optional[dict[str, Any]] = None,
    suggestion: Optional[str] = None,
    request_id: Optional[str] = None,
    upstream: Optional[dict[str, Any]] = None,
    include_detail: bool = True,
) -> dict[str, Any]:
    """Build a Phase-A compatible error response with both ``detail`` and ``error``.

    During the compatibility period (Phase A), all Relay API error responses
    include the legacy top-level ``detail`` field alongside the new standard
    ``error`` object.  Clients should migrate to ``error.code``.

    Parameters
    ----------
    code : str
        UniAPI error code.
    message : str
        Human-readable error message.
    details : dict, optional
        Structured context for ``error.details``.
    suggestion : str, optional
        Actionable fix suggestion for ``error.suggestion``.
    request_id : str, optional
        Explicit request ID.
    upstream : dict, optional
        Upstream error info.
    include_detail : bool
        When True (default), the legacy ``detail`` field is included.
        Set to False to omit it (e.g. for Phase B or management API).

    Returns
    -------
    dict
        Response dict with ``success``, ``detail`` (if include_detail), and ``error``.
    """
    base = build_error_response(
        code=code,
        message=message,
        details=details,
        suggestion=suggestion,
        request_id=request_id,
        upstream=upstream,
    )

    if include_detail:
        # Insert detail before error for readability
        result: dict[str, Any] = {"detail": message}
        result.update(base)
        return result

    return base
