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
) -> Tuple[str, dict[str, Any], Optional[str]]:
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
    tuple[str, dict, str | None]
        (uni_api_code, upstream_dict, reason)
        The third element is a human-readable reason for ``details.reason``.
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
        return uni_api_code, _build_upstream(provider, status_code, upstream_code, upstream_message), "请求内容被上游安全/内容过滤拦截"

    # Map by status code
    uni_api_code = _http_status_to_upstream_code(status_code)

    # Build a human-readable reason from upstream context
    reason = _build_reason(uni_api_code, provider, status_code, upstream_code, upstream_message)

    return uni_api_code, _build_upstream(provider, status_code, upstream_code, upstream_message), reason


def _http_status_to_upstream_code(status_code: int) -> str:
    """Map an upstream HTTP status code to a UniAPI upstream error code.

    Mapping rules:
    - 400/422 → ``UNIAPI_INVALID_REQUEST``: the converted request body was
      rejected by the upstream (e.g. GLM doesn't support a field).  Client
      should fix their request, not retry blindly.
    - 401/403 → ``UPSTREAM_BAD_RESPONSE``: likely a channel API key issue.
    - 404     → ``UNIAPI_MODEL_NOT_SUPPORTED``.
    - 429     → ``UPSTREAM_RATE_LIMITED``.
    - 5xx/504 → ``UPSTREAM_TIMEOUT`` / ``UPSTREAM_UNAVAILABLE``.
    """
    if status_code == 429:
        return "UPSTREAM_RATE_LIMITED"
    if status_code == 404:
        return "UNIAPI_MODEL_NOT_SUPPORTED"
    if status_code == 504:
        return "UPSTREAM_TIMEOUT"
    if status_code in (500, 502, 503):
        return "UPSTREAM_UNAVAILABLE"
    if status_code in (400, 422):
        return "UNIAPI_INVALID_REQUEST"
    if status_code in (401, 403):
        return "UPSTREAM_BAD_RESPONSE"
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
    tuple[str, dict, str | None]
        (uni_api_code, upstream_dict, reason)
    """
    timeout_types = {"timeout", "read_timeout", "connect_timeout", "write_timeout"}
    connection_failure_types = {"connection_refused", "connection_reset", "dns_error"}

    if error_type in timeout_types:
        code = "UPSTREAM_TIMEOUT"
    elif error_type in connection_failure_types:
        code = "UPSTREAM_CONNECTION_FAILED"
    else:
        code = "UPSTREAM_BAD_RESPONSE"

    reason = f"上游 {provider} 连接{error_type}，请求无法到达供应商。"
    return code, _build_upstream(provider, 0), reason


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


def _build_reason(
    uni_code: str,
    provider: str,
    status_code: int,
    upstream_code: str | None,
    upstream_message: str | None,
) -> str | None:
    """Build a human-readable reason for ``error.details.reason``.

    Returns None when the reason would be redundant with ``error.message``.
    """
    if uni_code == "UNIAPI_INVALID_REQUEST":
        msg = upstream_message or f"HTTP {status_code}"
        return f"上游 {provider} 拒绝请求：{msg}。请检查参数格式是否正确。"
    if uni_code == "UPSTREAM_RATE_LIMITED":
        return f"上游 {provider} 速率限制，建议稍后重试。"
    if uni_code == "UPSTREAM_TIMEOUT":
        return f"上游 {provider} 响应超时，可能是模型负载过高。"
    if uni_code == "UPSTREAM_UNAVAILABLE":
        if upstream_message:
            return f"上游 {provider} 暂时不可用：{upstream_message}"
        return f"上游 {provider} 暂时不可用（HTTP {status_code}），建议稍后重试。"
    if uni_code == "UPSTREAM_BAD_RESPONSE":
        return f"上游 {provider} 返回异常（HTTP {status_code}），请联系管理员检查渠道配置。"
    if upstream_message:
        return f"上游 {provider}: {upstream_message}"
    return None
