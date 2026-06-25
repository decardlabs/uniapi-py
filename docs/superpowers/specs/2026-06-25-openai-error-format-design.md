# OpenAI-Compatible Error Format for /v1/* Endpoints

**Date**: 2026-06-25
**Status**: Draft

## Problem Statement

When a UniAPI token has model restrictions (e.g., only "MiniMax-M3" allowed) and
a client requests an unauthorized model (e.g., "deepseek-v4-pro"), UniAPI returns:

  - HTTP `403 Forbidden`
  - Error type `"authorization"`
  - Error code `"UNIAPI_TOKEN_MODEL_NOT_ALLOWED"`

OpenAI-compatible clients (Claude Code, OpenWebUI, LobeChat, etc.) interpret
the 403 + `"authorization"` type as **authentication failure**, causing them to
discard the API key and prompt re-login instead of gracefully reporting that
the requested model is not accessible.

OpenAI itself returns a `404` with `model_not_found` for this scenario, which
clients handle correctly (no re-login prompt).

## Scope

All `/v1/*` endpoints (the OpenAI-compatible relay API).

Non-excluded: Management API (`/api/*`) keeps the existing UniAPI error format.

## Design

### Architecture

```
RelayException raised (in relay.py, any /v1/* path)
  → app_exception_handler(request, exc)
    → request.url.path starts with "/v1/"
      → OPENAI FORMAT:
        → map UniAPI code → (status, openai_type, openai_code)
        → build OpenAI-compatible error response JSON
        → return JSONResponse(status_code=openai_status, content=openai_body)
    → else (management API /api/*)
      → UNIAPI FORMAT (unchanged):
        → build_compat_error_response(exc)
        → return JSONResponse(status_code=exc.status_code, content=uniabi_body)
```

### OpenAI Error Response Format

Per [OpenAI API errors](https://platform.openai.com/docs/guides/error-codes/api-errors):

```json
{
  "error": {
    "message": "The model `deepseek-v4-pro` does not exist or you do not have access to it.",
    "type": "invalid_request_error",
    "param": null,
    "code": "model_not_found"
  }
}
```

Fields:
- `error.message` — human-readable description (taken from `exc.message`)
- `error.type` — category string from OpenAI's taxonomy (e.g. `invalid_request_error`, `authentication_error`)
- `error.param` — `null` (always; UniAPI doesn't expose parameter-level errors in OpenAI format)
- `error.code` — machine-readable error code from OpenAI's taxonomy (e.g. `model_not_found`, `invalid_api_key`)

### Error Code Mapping

| UniAPI Code | HTTP | OpenAI type | OpenAI code |
|---|---|---|---|
| `UNIAPI_TOKEN_MODEL_NOT_ALLOWED` | 404 | `invalid_request_error` | `model_not_found` |
| `UNIAPI_MODEL_NOT_SPECIFIED` | 400 | `invalid_request_error` | `model_not_found` |
| `UNIAPI_MODEL_NOT_SUPPORTED` | 404 | `invalid_request_error` | `model_not_found` |
| `UNIAPI_INVALID_TOKEN` | 401 | `authentication_error` | `invalid_api_key` |
| `UNIAPI_TOKEN_EXPIRED` | 401 | `authentication_error` | `invalid_api_key` |
| `UNIAPI_ADMIN_REQUIRED` | 403 | `authorization_error` | `permission_denied` |
| `UNIAPI_GROUP_ACCESS_DENIED` | 403 | `authorization_error` | `permission_denied` |
| `UNIAPI_INVALID_REQUEST` | 400 | `invalid_request_error` | `invalid_request_error` |
| `UNIAPI_RESOURCE_NOT_FOUND` | 404 | `not_found_error` | `resource_not_found` |
| `UNIAPI_QUOTA_EXHAUSTED` | 429 | `insufficient_quota` | `insufficient_quota` |
| `UNIAPI_RATE_LIMITED` | 429 | `rate_limit_error` | `rate_limit_exceeded` |
| `UNIAPI_SERVICE_DISABLED` | 503 | `api_error` | `server_error` |
| `UNIAPI_CHANNEL_UNAVAILABLE` | 503 | `api_error` | `server_error` |
| `UPSTREAM_TIMEOUT` | 504 | `api_error` | `upstream_error` |
| `UPSTREAM_UNAVAILABLE` | 503 | `api_error` | `upstream_error` |
| `UPSTREAM_BAD_RESPONSE` | 502 | `api_error` | `upstream_error` |
| `UPSTREAM_RATE_LIMITED` | 429 | `rate_limit_error` | `upstream_error` |
| `UPSTREAM_CONNECTION_FAILED` | 502 | `api_error` | `upstream_error` |

Notable changes from current UniAPI behavior:
- `UNIAPI_TOKEN_MODEL_NOT_ALLOWED`: **403→404**, `authorization`→`invalid_request_error` — fixes the core Claude Code issue
- `UNIAPI_MODEL_NOT_SUPPORTED`: **400→404** — matches OpenAI convention
- `UNIAPI_QUOTA_EXHAUSTED`: **402→429** — 402 is non-standard HTTP

Default fallback for unknown codes: `(500, "api_error", "server_error")`.

### Files Changed

**New file: `app/schemas/openai_error.py`**

Contains:
- `OPENAI_ERROR_MAP: dict[str, tuple[int, str, str]]` — mapping table
- `get_openai_error_meta(code: str) -> tuple[int, str, str]` — lookup function
- `build_openai_error_response(message, openai_type, openai_code, param) -> dict` — response builder

**Modified file: `app/exceptions.py`**

- `app_exception_handler()`: add `/v1/*` branch before existing logic

**Unchanged:**
- `app/routers/v1/relay.py` — exception raise sites unchanged
- `app/error_codes.py` — constants unchanged
- `app/schemas/error.py` — `build_compat_error_response` preserved for management API
- `app/dependencies.py` — auth errors flow through the same handler

### Edge Cases

1. **UpstreamException on /v1/***: maps to `api_error` / `upstream_error`; the upstream detail is logged server-side only (not exposed in OpenAI format)
2. **HTTPException (FastAPI built-in)**: handled by `http_exception_handler`, which already produces compat format; no change needed
3. **Provider-specific error codes (`PROVIDER_*`)**: treated as unknown → fallback (500 / `api_error` / `server_error`)
4. **Nonexistent mapping key**: default fallback applies; no crash

## Testing

### Test Scenarios

1. `UNIAPI_TOKEN_MODEL_NOT_ALLOWED` → HTTP 404, `error.code`=`model_not_found`, `error.type`=`invalid_request_error`
2. `UNIAPI_INVALID_TOKEN` → HTTP 401, `error.code`=`invalid_api_key`
3. `UNIAPI_MODEL_NOT_SUPPORTED` → HTTP 404
4. `UNIAPI_QUOTA_EXHAUSTED` → HTTP 429
5. `/api/*` endpoints → unchanged UniAPI format (regression check)
6. Unknown error code → 500 fallback
7. `/v1/models` listing still correctly filters by token permissions (no regression)

### Existing Tests

Tests that assert specific response body content on `/v1/*` paths (e.g., checking for `success: false` or `error.code == "UNIAPI_TOKEN_MODEL_NOT_ALLOWED"`) will need to be updated to match the new OpenAI format.

Tests that only check HTTP status codes will pass without changes.

