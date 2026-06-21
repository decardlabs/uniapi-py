"""Upstream error mapping — classify upstream provider errors into UniAPI codes.

Maps upstream HTTP responses and connection failures to the standard
UniAPI error code space (spec §7.2).  The original upstream error
details are preserved in an ``upstream`` dict for trace correlation.

See: docs/error-codes/UNIAPI_ERROR_CODE_SPEC_DRAFT.md
"""

from __future__ import annotations

from typing import Any, Optional, Tuple


# ── HTTP status → UniAPI code ────────────────────────────────────────────────


def map_upstream_http_error(
    provider: str,
    status_code: int,
    response_body: Any = None,
) -> Tuple[str, dict[str, Any]]:
    """Map an upstream HTTP error response to a UniAPI error code.

    Parameters
    ----------
    provider : str
        Upstream provider name (lowercase), e.g. ``"deepseek"``.
    status_code : int
        HTTP status code from the upstream response.
    response_body : any, optional
        Parsed response body (dict, str, or None).

    Returns
    -------
    tuple[str, dict]
        (uni_api_code, upstream_dict)
    """
    # Extract upstream error info from response body
    upstream_code: Optional[str] = None
    upstream_message: Optional[str] = None

    if isinstance(response_body, dict):
        err = response_body.get("error") or {}
        if isinstance(err, dict):
            upstream_code = err.get("code")
            upstream_message = err.get("message")
    elif isinstance(response_body, str):
        upstream_message = response_body

    # Check for safety / content filter blocks (provider-specific)
    if upstream_code == "content_filter" and status_code in (400, 403):
        uni_api_code = f"PROVIDER_{provider.upper()}_SAFETY_BLOCKED"
        return uni_api_code, _build_upstream(provider, status_code, upstream_code, upstream_message)

    # Map by status code
    uni_api_code = _http_status_to_upstream_code(status_code)

    return uni_api_code, _build_upstream(provider, status_code, upstream_code, upstream_message)


def _http_status_to_upstream_code(status_code: int) -> str:
    """Map an upstream HTTP status code to a UniAPI upstream error code."""
    if status_code == 429:
        return "UPSTREAM_RATE_LIMITED"
    if status_code == 404:
        return "UNIAPI_MODEL_NOT_SUPPORTED"
    if status_code == 504:
        return "UPSTREAM_TIMEOUT"
    if status_code in (500, 502, 503):
        return "UPSTREAM_UNAVAILABLE"
    if 400 <= status_code < 500:
        return "UPSTREAM_BAD_RESPONSE"
    return "UPSTREAM_UNAVAILABLE"


# ── Connection error → UniAPI code ───────────────────────────────────────────


def map_upstream_connection_error(
    provider: str,
    error_type: str,
) -> Tuple[str, dict[str, Any]]:
    """Map an upstream connection/network error to a UniAPI error code.

    Parameters
    ----------
    provider : str
        Upstream provider name (lowercase).
    error_type : str
        Connection error classifier: ``"timeout"``, ``"read_timeout"``,
        ``"connect_timeout"``, ``"connection_refused"``, ``"connection_reset"``,
        ``"dns_error"``, or any other string (falls back to ``UPSTREAM_BAD_RESPONSE``).

    Returns
    -------
    tuple[str, dict]
        (uni_api_code, upstream_dict)
    """
    timeout_types = {"timeout", "read_timeout", "connect_timeout", "write_timeout"}
    connection_failure_types = {"connection_refused", "connection_reset", "dns_error"}

    if error_type in timeout_types:
        code = "UPSTREAM_TIMEOUT"
    elif error_type in connection_failure_types:
        code = "UPSTREAM_CONNECTION_FAILED"
    else:
        code = "UPSTREAM_BAD_RESPONSE"

    return code, _build_upstream(provider, 0)


# ── Utility: extract upstream info from httpx response ───────────────────────


def extract_upstream_info(provider: str, response: Any) -> dict[str, Any]:
    """Extract upstream error detail from an ``httpx.Response``.

    Parameters
    ----------
    provider : str
        Upstream provider name (lowercase).
    response : httpx.Response
        The upstream response object.

    Returns
    -------
    dict
        Upstream dict ready for ``UpstreamErrorDetail`` or
        ``UpstreamException``.
    """
    upstream_code: Optional[str] = None
    upstream_message: Optional[str] = None

    try:
        body = response.json()
        if isinstance(body, dict):
            err = body.get("error") or {}
            if isinstance(err, dict):
                upstream_code = err.get("code")
                upstream_message = err.get("message")
    except (ValueError, AttributeError):
        try:
            upstream_message = response.text or None
        except Exception:
            pass

    # Try to capture upstream request ID from headers
    upstream_request_id: Optional[str] = None
    try:
        upstream_request_id = response.headers.get("X-Request-Id") or response.headers.get("x-request-id")
    except Exception:
        pass

    return _build_upstream(
        provider,
        response.status_code,
        upstream_code,
        upstream_message,
        upstream_request_id,
    )


# ── Internal helpers ─────────────────────────────────────────────────────────


def _build_upstream(
    provider: str,
    status_code: int,
    code: Optional[str] = None,
    message: Optional[str] = None,
    request_id: Optional[str] = None,
) -> dict[str, Any]:
    """Build a cleaned upstream dict, omitting None values."""
    result: dict[str, Any] = {
        "provider": provider,
        "status_code": status_code,
    }
    if code is not None:
        result["code"] = code
    if message is not None:
        result["message"] = message
    if request_id is not None:
        result["request_id"] = request_id
    return result
