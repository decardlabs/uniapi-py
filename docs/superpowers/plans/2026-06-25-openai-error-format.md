# OpenAI-Compatible Error Format Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Return OpenAI-standard error responses on `/v1/*` endpoints so that OpenAI-compatible clients (Claude Code, OpenWebUI, LobeChat) correctly interpret model permission errors instead of treating them as auth failures.

**Architecture:** Add a new `app/schemas/openai_error.py` module with a UniAPI→OpenAI error code mapping table and response builder. In `app/exceptions.py`, branch on `request.url.path` in both `app_exception_handler` and `http_exception_handler` — `/v1/*` paths return OpenAI format, all other paths keep the existing UniAPI format unchanged.

**Tech Stack:** Python 3.10+, FastAPI, Pydantic v2 (nonew dependencies)

**Methodology:** TDD — write the failing test, verify failure, write implementation, verify pass, commit.

## Global Constraints

- No changes to `app/error_codes.py` — error code constants and mapping table are preserved for the management API
- No changes to `app/schemas/error.py` — `build_error_response` and `build_compat_error_response` are preserved for non-`/v1/*` paths
- No changes to `app/routers/v1/relay.py` — exception raise sites unchanged
- The OpenAI error format must match OpenAI's documented spec: `{"error": {"message": str, "type": str, "param": null, "code": str}}`
- Management API (`/api/*`) must continue to return the existing UniAPI error format unchanged

---

### Task 1: Create `app/schemas/openai_error.py` with mapping + builder

**Files:**
- Create: `app/schemas/openai_error.py`
- Create: `tests/phase5/test_openai_error.py`

**Interfaces:**
- Produces: `OPENAI_ERROR_MAP: dict[str, tuple[int, str, str]]` — mapping table
- Produces: `get_openai_error_meta(code: str) -> tuple[int, str, str]` — lookup function
- Produces: `build_openai_error_response(message, openai_type, openai_code, param=None) -> dict` — response builder

The test must be written first and verified to fail before implementing.

- [ ] **Step 1: Write the failing test**

```python
"""Tests for app/schemas/openai_error.py — OpenAI-compatible error response."""

import pytest
from app.schemas.openai_error import (
    OPENAI_ERROR_MAP,
    get_openai_error_meta,
    build_openai_error_response,
)


class TestGetOpenAIErrorMeta:
    """get_openai_error_meta maps UniAPI codes to OpenAI format."""

    def test_model_not_allowed_maps_to_404_model_not_found(self):
        status, type_, code = get_openai_error_meta("UNIAPI_TOKEN_MODEL_NOT_ALLOWED")
        assert status == 404
        assert type_ == "invalid_request_error"
        assert code == "model_not_found"

    def test_invalid_token_maps_to_401_invalid_api_key(self):
        status, type_, code = get_openai_error_meta("UNIAPI_INVALID_TOKEN")
        assert status == 401
        assert type_ == "authentication_error"
        assert code == "invalid_api_key"

    def test_quota_exhausted_maps_to_429_insufficient_quota(self):
        status, type_, code = get_openai_error_meta("UNIAPI_QUOTA_EXHAUSTED")
        assert status == 429
        assert type_ == "insufficient_quota"
        assert code == "insufficient_quota"

    def test_model_not_supported_maps_to_404_model_not_found(self):
        status, type_, code = get_openai_error_meta("UNIAPI_MODEL_NOT_SUPPORTED")
        assert status == 404
        assert type_ == "invalid_request_error"
        assert code == "model_not_found"

    def test_rate_limited_maps_to_429_rate_limit_exceeded(self):
        status, type_, code = get_openai_error_meta("UNIAPI_RATE_LIMITED")
        assert status == 429
        assert type_ == "rate_limit_error"
        assert code == "rate_limit_exceeded"

    def test_channel_unavailable_maps_to_503_server_error(self):
        status, type_, code = get_openai_error_meta("UNIAPI_CHANNEL_UNAVAILABLE")
        assert status == 503
        assert type_ == "api_error"
        assert code == "server_error"

    def test_unknown_code_falls_back_to_500(self):
        status, type_, code = get_openai_error_meta("UNIAPI_DOES_NOT_EXIST")
        assert status == 500
        assert type_ == "api_error"
        assert code == "server_error"

    def test_every_entry_has_valid_status(self):
        """All mapped codes produce 4xx or 5xx status codes."""
        for code in OPENAI_ERROR_MAP:
            status, _, _ = get_openai_error_meta(code)
            assert 400 <= status < 600, f"{code} has invalid status {status}"

    def test_token_expired_maps_to_401_invalid_api_key(self):
        status, type_, code = get_openai_error_meta("UNIAPI_TOKEN_EXPIRED")
        assert status == 401
        assert type_ == "authentication_error"
        assert code == "invalid_api_key"

    def test_admin_required_maps_to_403_permission_denied(self):
        status, type_, code = get_openai_error_meta("UNIAPI_ADMIN_REQUIRED")
        assert status == 403
        assert type_ == "authorization_error"
        assert code == "permission_denied"

    def test_group_access_denied_maps_to_403_permission_denied(self):
        status, type_, code = get_openai_error_meta("UNIAPI_GROUP_ACCESS_DENIED")
        assert status == 403
        assert type_ == "authorization_error"
        assert code == "permission_denied"

    def test_invalid_request_maps_to_400_invalid_request_error(self):
        status, type_, code = get_openai_error_meta("UNIAPI_INVALID_REQUEST")
        assert status == 400
        assert type_ == "invalid_request_error"
        assert code == "invalid_request_error"

    def test_resource_not_found_maps_to_404_not_found(self):
        status, type_, code = get_openai_error_meta("UNIAPI_RESOURCE_NOT_FOUND")
        assert status == 404
        assert type_ == "not_found_error"
        assert code == "resource_not_found"

    def test_service_disabled_maps_to_503_server_error(self):
        status, type_, code = get_openai_error_meta("UNIAPI_SERVICE_DISABLED")
        assert status == 503
        assert type_ == "api_error"
        assert code == "server_error"

    def test_model_not_specified_maps_to_400_model_not_found(self):
        status, type_, code = get_openai_error_meta("UNIAPI_MODEL_NOT_SPECIFIED")
        assert status == 400
        assert type_ == "invalid_request_error"
        assert code == "model_not_found"


class TestBuildOpenAIErrorResponse:
    """build_openai_error_response produces correct OpenAI format."""

    def test_returns_correct_structure(self):
        result = build_openai_error_response(
            message="Test error",
            openai_type="invalid_request_error",
            openai_code="model_not_found",
        )
        assert "error" in result
        assert result["error"]["message"] == "Test error"
        assert result["error"]["type"] == "invalid_request_error"
        assert result["error"]["param"] is None
        assert result["error"]["code"] == "model_not_found"

    def test_empty_message(self):
        result = build_openai_error_response(
            message="",
            openai_type="api_error",
            openai_code="server_error",
        )
        assert result["error"]["message"] == ""

    def test_no_extra_fields(self):
        """OpenAI format should only have the standard 4 fields."""
        result = build_openai_error_response(
            message="msg",
            openai_type="t",
            openai_code="c",
        )
        error = result["error"]
        assert set(error.keys()) == {"message", "type", "param", "code"}
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/phase5/test_openai_error.py -v --no-header
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.schemas.openai_error'`

- [ ] **Step 3: Write minimal implementation**

Create `app/schemas/openai_error.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/phase5/test_openai_error.py -v --no-header
```

Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add app/schemas/openai_error.py tests/phase5/test_openai_error.py
git commit -m "feat: add OpenAI-compatible error response module"
```

---

### Task 2: Modify `app/exceptions.py` to return OpenAI format on /v1/* paths

**Files:**
- Modify: `app/exceptions.py` (app_exception_handler and http_exception_handler)
- Modify: `tests/phase5/test_exception_handler.py` (keep existing tests, add /v1/ path tests)

**Interfaces:**
- Consumes: `get_openai_error_meta(code) -> (int, str, str)` from Task 1
- Consumes: `build_openai_error_response(message, openai_type, openai_code, param) -> dict` from Task 1
- Pre-existing: `_http_status_to_code(status_code) -> str` — unchanged

- [ ] **Step 1: Add test for /v1/ paths producing OpenAI format**

Append to `tests/phase5/test_exception_handler.py` **before** (or at the end of) the existing tests:

```python
class TestOpenAIFormatOnV1Paths:
    """/v1/* paths produce OpenAI-compatible error format."""

    async def test_v1_path_returns_openai_format(self, client):
        resp = await client.get("/v1/raise/relay")
        assert resp.status_code == 404
        data = resp.json()
        # OpenAI format: only "error" at top level
        assert list(data.keys()) == ["error"]
        assert data["error"]["message"] == "Token not allowed"
        assert data["error"]["type"] == "invalid_request_error"
        assert data["error"]["param"] is None
        assert data["error"]["code"] == "model_not_found"

    async def test_v1_path_unauthorized_returns_openai_format(self, client):
        resp = await client.get("/v1/raise/unauthorized")
        assert resp.status_code == 401
        data = resp.json()
        assert data["error"]["code"] == "invalid_api_key"
        assert data["error"]["type"] == "authentication_error"

    async def test_v1_path_quota_returns_429(self, client):
        resp = await client.get("/v1/raise/quota")
        assert resp.status_code == 429
        data = resp.json()
        assert data["error"]["code"] == "insufficient_quota"
        assert data["error"]["type"] == "insufficient_quota"

    async def test_v1_path_upstream(self, client):
        resp = await client.get("/v1/raise/upstream")
        assert resp.status_code == 504
        data = resp.json()
        assert data["error"]["code"] == "upstream_error"
        assert data["error"]["type"] == "api_error"

    async def test_v1_path_http_401(self, client):
        resp = await client.get("/v1/raise/http-401")
        assert resp.status_code == 401
        data = resp.json()
        assert data["error"]["code"] == "invalid_api_key"
        assert data["error"]["type"] == "authentication_error"

    async def test_v1_path_http_403(self, client):
        resp = await client.get("/v1/raise/http-403")
        assert resp.status_code == 403
        data = resp.json()
        assert data["error"]["code"] == "permission_denied"
        assert data["error"]["type"] == "authorization_error"

    async def test_v1_path_http_429(self, client):
        resp = await client.get("/v1/raise/http-429")
        assert resp.status_code == 429
        data = resp.json()
        assert data["error"]["code"] == "rate_limit_exceeded"
        assert data["error"]["type"] == "rate_limit_error"

    async def test_non_v1_path_unchanged(self, client):
        """AppException on non-/v1 path still produces UniAPI format."""
        resp = await client.get("/raise/app")
        assert resp.status_code == 400
        data = resp.json()
        assert data["success"] is False
        assert data["error"]["code"] == "UNIAPI_INVALID_REQUEST"
        assert data["error"]["type"] == "validation"
        assert "request_id" in data["error"]

    async def test_non_v1_relay_exception_still_has_compat(self, client):
        """RelayException on non-/v1 path still produces compat format."""
        resp = await client.get("/raise/relay")
        assert resp.status_code == 403
        data = resp.json()
        assert "detail" in data
        assert data["error"]["code"] == "UNIAPI_TOKEN_MODEL_NOT_ALLOWED"
        assert data["error"]["type"] == "authorization"
```

Also need to add `/v1/` versions of the route handlers. Modify the test helper `_build_test_app` to add `/v1/raise/*` endpoints:

```python
# Inside _build_test_app(), add after the existing routes:
    @app.get("/v1/raise/relay")
    async def raise_v1_relay():
        from app.exceptions import RelayException
        raise RelayException(
            message="Token not allowed",
            code="UNIAPI_TOKEN_MODEL_NOT_ALLOWED",
        )

    @app.get("/v1/raise/unauthorized")
    async def raise_v1_unauthorized():
        from app.exceptions import UnauthorizedException
        raise UnauthorizedException()

    @app.get("/v1/raise/quota")
    async def raise_v1_quota():
        from app.exceptions import QuotaExceededException
        raise QuotaExceededException(message="Insufficient quota")

    @app.get("/v1/raise/upstream")
    async def raise_v1_upstream():
        from app.exceptions import UpstreamException
        raise UpstreamException(
            message="Upstream timed out",
            upstream_provider="deepseek",
            upstream_status=504,
        )

    @app.get("/v1/raise/http-401")
    async def raise_v1_http_401():
        raise HTTPException(status_code=401, detail="Not logged in")

    @app.get("/v1/raise/http-403")
    async def raise_v1_http_403():
        raise HTTPException(status_code=403, detail="Admin required")

    @app.get("/v1/raise/http-429")
    async def raise_v1_http_429():
        raise HTTPException(status_code=429, detail="Rate limited")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/phase5/test_exception_handler.py::TestOpenAIFormatOnV1Paths -v --no-header
```

Expected: FAIL — the /v1/ endpoints still return old format because the handler hasn't been updated yet.

- [ ] **Step 3: Modify `app_exception_handler` and `http_exception_handler` in `app/exceptions.py`**

Change the `app_exception_handler` function:

```python
async def app_exception_handler(request, exc: AppException) -> JSONResponse:
    from app.schemas.error import build_compat_error_response, build_error_response
    from app.schemas.openai_error import get_openai_error_meta, build_openai_error_response

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
            include_detail=True,
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
```

Change the `http_exception_handler` function:

```python
async def http_exception_handler(request, exc) -> JSONResponse:
    from fastapi import HTTPException
    from app.schemas.error import build_compat_error_response
    from app.schemas.openai_error import get_openai_error_meta, build_openai_error_response

    status_code = exc.status_code if isinstance(exc, HTTPException) else 500
    detail = exc.detail if isinstance(exc, HTTPException) else str(exc)
    request_id = getattr(request.state, "request_id", None) if hasattr(request, "state") else None
    is_v1_path = request.url.path.startswith("/v1/") if hasattr(request, "url") else False

    # /v1/* endpoints → OpenAI-compatible error format
    if is_v1_path:
        code = _http_status_to_code(status_code)
        _, openai_type, openai_code = get_openai_error_meta(code)
        resp = build_openai_error_response(
            message=detail if isinstance(detail, str) else str(detail),
            openai_type=openai_type,
            openai_code=openai_code,
        )
        return JSONResponse(status_code=status_code, content=resp)

    # Non-/v1/* endpoints → UniAPI format (unchanged)
    code = _http_status_to_code(status_code)
    resp = build_compat_error_response(
        code=code,
        message=detail if isinstance(detail, str) else str(detail),
        request_id=request_id,
        include_detail=True,
    )
    return JSONResponse(status_code=status_code, content=resp)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/phase5/test_exception_handler.py -v --no-header
```

Expected: ALL tests PASS (both old non-/v1/ tests and new /v1/ tests)

- [ ] **Step 5: Run full phase5 test suite to check for regressions**

```bash
python -m pytest tests/phase5/ -v --no-header
```

Expected: Most pass. `test_relay_errors.py` may fail because it asserts on the old format for /v1/ paths. (Those will be fixed in Task 3.)

- [ ] **Step 6: Commit**

```bash
git add app/exceptions.py tests/phase5/test_exception_handler.py
git commit -m "feat: return OpenAI-compatible error format on /v1/* paths"
```

---

### Task 3: Update integration tests that assert on old /v1/ error format

**Files:**
- Modify: `tests/phase5/test_relay_errors.py`

The integration tests in `test_relay_errors.py` make real requests to `/v1/chat/completions` and assert response bodies. These need to be updated to match the new OpenAI format.

- [ ] **Step 1: Update test assertions**

Change `tests/phase5/test_relay_errors.py`:

In `test_model_not_supported`:
```python
    async def test_model_not_supported(self):
        """Requesting an unsupported model returns model_not_found."""
        resp = await self._post({"model": "nonexistent-model-xyz-123", "messages": [{"role": "user", "content": "hi"}]})
        assert resp.status_code in (400, 404), f"Got {resp.status_code}"
        data = resp.json()
        # OpenAI format: error.code = "model_not_found"
        assert data["error"]["code"] == "model_not_found", f"Got code: {data['error']['code']}"
        assert data["error"]["type"] == "invalid_request_error"
```

In `test_all_errors_include_request_id`:
```python
    async def test_all_errors_include_request_id(self):
        """Every relay error must contain error.request_id (in message if not in a field)."""
        resp = await self._post({"model": "nonexistent-model-xyz", "messages": [{"role": "user", "content": "hi"}]})
        data = resp.json()
        # OpenAI format doesn't have request_id field; instead verify message is non-empty
        assert data["error"]["message"], f"Message missing: {data['error']}"
```

In `test_phase_a_compat_detail_present` — **remove or rewrite** this test:
```python
    async def test_openai_format_no_extra_fields(self):
        """Phase B: v1 relay errors return pure OpenAI format (no detail/success)."""
        resp = await self._post({"model": "nonexistent-model-xyz", "messages": [{"role": "user", "content": "hi"}]})
        data = resp.json()
        assert list(data.keys()) == ["error"], f"Unexpected keys: {list(data.keys())}"
        assert set(data["error"].keys()) == {"message", "type", "param", "code"}, \
            f"Unexpected error keys: {list(data['error'].keys())}"
```

- [ ] **Step 2: Run test to verify it passes**

```bash
python -m pytest tests/phase5/test_relay_errors.py::TestRelayBusinessErrors -v --no-header
```

Expected: PASS

- [ ] **Step 3: Run full test suite**

```bash
python -m pytest tests/ -v --no-header
```

Expected: ALL tests pass (or only pre-existing failures unrelated to this change)

- [ ] **Step 4: Commit**

```bash
git add tests/phase5/test_relay_errors.py
git commit -m "test: update relay error tests for OpenAI-compatible format"
```

---

### Verification

```bash
# Full phase5 test suite
python -m pytest tests/phase5/ -v --no-header

# Specific relay error tests
python -m pytest tests/phase5/test_relay_errors.py -v --no-header

# Exception handler (old + new format)
python -m pytest tests/phase5/test_exception_handler.py -v --no-header

# OpenAI error module unit tests
python -m pytest tests/phase5/test_openai_error.py -v --no-header

# Schema tests (should be unaffected)
python -m pytest tests/phase5/test_error_schemas.py tests/phase5/test_error_snapshots.py -v --no-header
```
