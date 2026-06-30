"""UniAPI exception hierarchy with unified error codes.

Extends the original ``AppException`` with fields from the error code
spec so that every raised exception carries enough information to
produce a standard error response.

See: docs/error-codes/UNIAPI_ERROR_CODE_SPEC_DRAFT.md
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi.responses import JSONResponse

from app.error_codes import get_error_meta  # noqa: E402 — no circular dependency; error_codes only imports from typing.

# ── Base exception ───────────────────────────────────────────────────────────


class AppException(Exception):
    """Base application exception.

    All UniAPI exceptions should use this class or its subclasses so the
    global exception handler can produce a standard error response.
    """

    def __init__(
        self,
        status_code: int = 400,
        message: str = "Bad request",
        code: str = "UNIAPI_INVALID_REQUEST",
        type: str = "validation",
        details: Optional[dict[str, Any]] = None,
        suggestion: Optional[str] = None,
        upstream: Optional[dict[str, Any]] = None,
        data: Any = None,
    ):
        self.status_code = status_code
        self.message = message
        self.code = code
        self.type = type
        self.details = details
        self.suggestion = suggestion
        self.upstream = upstream
        self.data = data


# ── Legacy subclasses (management API) ───────────────────────────────────────


class NotFoundException(AppException):
    def __init__(self, message: str = "Not found"):
        super().__init__(
            status_code=404,
            message=message,
            code="UNIAPI_RESOURCE_NOT_FOUND",
            type="not_found",
        )


class UnauthorizedException(AppException):
    def __init__(self, message: str = "Unauthorized"):
        super().__init__(
            status_code=401,
            message=message,
            code="UNIAPI_INVALID_TOKEN",
            type="authentication",
        )


class ForbiddenException(AppException):
    def __init__(self, message: str = "Forbidden"):
        super().__init__(
            status_code=403,
            message=message,
            code="UNIAPI_ADMIN_REQUIRED",
            type="authorization",
        )


class QuotaExceededException(AppException):
    def __init__(self, message: str = "Quota exceeded"):
        super().__init__(
            status_code=402,
            message=message,
            code="UNIAPI_QUOTA_EXHAUSTED",
            type="quota",
        )


class NotImplementedException(AppException):
    def __init__(self, message: str = "Not implemented"):
        super().__init__(status_code=501, message=message)


# ── Relay API exceptions ─────────────────────────────────────────────────────


class RelayException(AppException):
    """Exception for Relay API (/v1/*) endpoints.

    Automatically infers ``status_code`` and ``type`` from ``code``
    via the error-code mapping table.  Explicit values take precedence.
    """

    def __init__(
        self,
        message: str = "Relay error",
        code: str = "UNIAPI_INTERNAL_ERROR",
        status_code: Optional[int] = None,
        type: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
        suggestion: Optional[str] = None,
        upstream: Optional[dict[str, Any]] = None,
    ):
        inferred_status, inferred_type = get_error_meta(code)
        super().__init__(
            status_code=status_code if status_code is not None else inferred_status,
            message=message,
            code=code,
            type=type if type is not None else inferred_type,
            details=details,
            suggestion=suggestion,
            upstream=upstream,
        )


class UpstreamException(RelayException):
    """Exception for upstream provider errors.

    Auto-constructs the ``upstream`` dict from provider-specific params
    and infers the error code from common HTTP status patterns when not
    explicitly provided.
    """

    def __init__(
        self,
        message: str = "Upstream error",
        code: Optional[str] = None,
        upstream_provider: str = "unknown",
        upstream_status: int = 0,
        upstream_code: Optional[str] = None,
        upstream_message: Optional[str] = None,
        upstream_request_id: Optional[str] = None,
        status_code: Optional[int] = None,
        type: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
        suggestion: Optional[str] = None,
    ):
        # Infer code from upstream_status when not given
        if code is None:
            code = _infer_upstream_code(upstream_status)

        super().__init__(
            message=message,
            code=code,
            status_code=status_code,
            type=type,
            details=details,
            suggestion=suggestion,
            upstream={
                "provider": upstream_provider,
                "status_code": upstream_status,
                "code": upstream_code,
                "message": upstream_message,
                "request_id": upstream_request_id,
            },
        )


def _infer_upstream_code(http_status: int) -> str:
    """Map an upstream HTTP status (or 0 for connection errors) to a UniAPI code."""
    if http_status == 429:
        return "UPSTREAM_RATE_LIMITED"
    if http_status == 504:
        return "UPSTREAM_TIMEOUT"
    if http_status == 502:
        return "UPSTREAM_BAD_RESPONSE"
    if http_status in (500, 503):
        return "UPSTREAM_UNAVAILABLE"
    if http_status == 0:
        return "UPSTREAM_CONNECTION_FAILED"
    if 400 <= http_status < 500:
        return "UPSTREAM_BAD_RESPONSE"
    return "UPSTREAM_UNAVAILABLE"


# ── Exception handler ────────────────────────────────────────────────────────


async def app_exception_handler(request, exc: AppException) -> JSONResponse:
    """FastAPI exception handler that produces standard error responses.

    ``/v1/*`` paths return OpenAI-compatible error format.
    Other paths return the standard UniAPI format.

    During Phase A (compat period), non-v1 RelayExceptions also output a
    top-level ``detail`` field for backwards compatibility.
    """
    from app.schemas.error import build_compat_error_response, build_error_response
    from app.schemas.openai_error import build_openai_error_response, get_openai_error_meta

    request_id = getattr(request.state, "request_id", None) if hasattr(request, "state") else None
    is_v1_path = request.url.path.startswith("/v1/") if hasattr(request, "url") else False

    # /v1/* endpoints → OpenAI-compatible error format
    if is_v1_path:
        status, openai_type, openai_code = get_openai_error_meta(exc.code)
        resp = build_openai_error_response(
            message=exc.message,
            openai_type=openai_type,
            openai_code=openai_code,
        )
        return JSONResponse(status_code=status, content=resp)

    # Non-/v1/* endpoints → UniAPI format (unchanged)
    use_compat = isinstance(exc, RelayException)

    if use_compat:
        resp = build_compat_error_response(
            code=exc.code,
            message=exc.message,
            details=exc.details,
            suggestion=exc.suggestion,
            request_id=request_id,
            upstream=exc.upstream,
            include_detail=True,  # Phase A compat
        )
    else:
        resp = build_error_response(
            code=exc.code,
            message=exc.message,
            details=exc.details,
            suggestion=exc.suggestion,
            request_id=request_id,
            upstream=exc.upstream,
        )

    return JSONResponse(status_code=exc.status_code, content=resp)


async def http_exception_handler(request, exc) -> JSONResponse:  # type: ignore[no-untyped-def]
    """Map FastAPI's built-in ``HTTPException`` to a standard error format.

    ``/v1/*`` paths return OpenAI-compatible error format.
    Other paths return the standard UniAPI format.

    Registered alongside ``app_exception_handler`` in ``app/main.py``.
    """
    from fastapi import HTTPException

    from app.schemas.error import build_compat_error_response
    from app.schemas.openai_error import build_openai_error_response, get_openai_error_meta

    # Map HTTP status → UniAPI code
    status_code = exc.status_code if isinstance(exc, HTTPException) else 500
    detail = exc.detail if isinstance(exc, HTTPException) else str(exc)

    code = _http_status_to_code(status_code)

    request_id = getattr(request.state, "request_id", None) if hasattr(request, "state") else None
    is_v1_path = request.url.path.startswith("/v1/") if hasattr(request, "url") else False

    # /v1/* endpoints → OpenAI-compatible error format
    if is_v1_path:
        _, openai_type, openai_code = get_openai_error_meta(code)
        resp = build_openai_error_response(
            message=detail if isinstance(detail, str) else str(detail),
            openai_type=openai_type,
            openai_code=openai_code,
        )
        return JSONResponse(status_code=status_code, content=resp)

    # Non-/v1/* endpoints → UniAPI format (unchanged)
    resp = build_compat_error_response(
        code=code,
        message=detail if isinstance(detail, str) else str(detail),
        request_id=request_id,
        include_detail=True,  # Phase A compat for all HTTPException sources
    )

    return JSONResponse(status_code=status_code, content=resp)


def _http_status_to_code(status_code: int) -> str:
    """Map a raw HTTP status code to the closest UniAPI error code."""
    if status_code == 401:
        return "UNIAPI_INVALID_TOKEN"
    if status_code == 402:
        return "UNIAPI_QUOTA_EXHAUSTED"
    if status_code == 403:
        return "UNIAPI_ADMIN_REQUIRED"
    if status_code == 404:
        return "UNIAPI_RESOURCE_NOT_FOUND"
    if status_code == 422:
        return "UNIAPI_INVALID_REQUEST"
    if status_code == 429:
        return "UNIAPI_RATE_LIMITED"
    if status_code == 500:
        return "UNIAPI_INTERNAL_ERROR"
    if status_code == 502:
        return "UPSTREAM_BAD_RESPONSE"
    if status_code == 503:
        return "UPSTREAM_UNAVAILABLE"
    if status_code == 504:
        return "UPSTREAM_TIMEOUT"
    if 400 <= status_code < 500:
        return "UNIAPI_INVALID_REQUEST"
    return "UNIAPI_INTERNAL_ERROR"
