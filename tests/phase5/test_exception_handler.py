"""Phase 5, Tasks 1.3 & 1.4: Tests for exception handlers."""

import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient


# ── Helper to build a minimal test app ───────────────────────────────────────


def _build_test_app(register_http_handler: bool = True):
    """Create a minimal FastAPI app with the standard error handlers registered."""
    app = FastAPI()

    from app.exceptions import AppException, app_exception_handler

    app.add_exception_handler(AppException, app_exception_handler)

    if register_http_handler:
        from app.exceptions import http_exception_handler

        app.add_exception_handler(HTTPException, http_exception_handler)

    # Middleware that sets request.state.request_id (like RequestIDMiddleware)
    @app.middleware("http")
    async def _fake_request_id(request: Request, call_next):
        request.state.request_id = "req_test_handler_123"
        response = await call_next(request)
        return response

    # Routes that raise various exceptions
    @app.get("/raise/app")
    async def raise_app():
        raise AppException(status_code=400, message="Bad input", code="UNIAPI_INVALID_REQUEST", type="validation")

    @app.get("/raise/relay")
    async def raise_relay():
        from app.exceptions import RelayException

        raise RelayException(
            message="Token not allowed",
            code="UNIAPI_TOKEN_MODEL_NOT_ALLOWED",
        )

    @app.get("/raise/upstream")
    async def raise_upstream():
        from app.exceptions import UpstreamException

        raise UpstreamException(
            message="Upstream timed out",
            upstream_provider="deepseek",
            upstream_status=504,
        )

    @app.get("/raise/not-found")
    async def raise_not_found():
        from app.exceptions import NotFoundException

        raise NotFoundException(message="User not found")

    @app.get("/raise/unauthorized")
    async def raise_unauthorized():
        from app.exceptions import UnauthorizedException

        raise UnauthorizedException()

    @app.get("/raise/quota")
    async def raise_quota():
        from app.exceptions import QuotaExceededException

        raise QuotaExceededException(message="Insufficient quota")

    @app.get("/raise/http-401")
    async def raise_http_401():
        raise HTTPException(status_code=401, detail="Not logged in")

    @app.get("/raise/http-403")
    async def raise_http_403():
        raise HTTPException(status_code=403, detail="Admin required")

    @app.get("/raise/http-429")
    async def raise_http_429():
        raise HTTPException(status_code=429, detail="Rate limited")

    @app.get("/raise/http-500")
    async def raise_http_500():
        raise HTTPException(status_code=500, detail="Internal server error")

    # /v1/ route handlers — used by TestOpenAIFormatOnV1Paths
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

    return app


# ── Test fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
async def client():
    app = _build_test_app(register_http_handler=True)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def client_no_http_handler():
    """Client without HTTPException → standard format mapping."""
    app = _build_test_app(register_http_handler=False)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ── AppException handler tests ───────────────────────────────────────────────


class TestAppExceptionHandler:
    """Task 1.3: app_exception_handler produces standard error format."""

    async def test_handler_returns_standard_error_format(self, client):
        resp = await client.get("/raise/app")
        assert resp.status_code == 400
        data = resp.json()
        assert data["success"] is False
        assert data["error"]["code"] == "UNIAPI_INVALID_REQUEST"
        assert data["error"]["message"] == "Bad input"
        assert data["error"]["type"] == "validation"
        assert data["error"]["status_code"] == 400

    async def test_handler_includes_request_id(self, client):
        resp = await client.get("/raise/app")
        data = resp.json()
        assert data["error"]["request_id"] == "req_test_handler_123"

    async def test_handler_not_found_subclass(self, client):
        resp = await client.get("/raise/not-found")
        assert resp.status_code == 404
        data = resp.json()
        assert data["error"]["code"] == "UNIAPI_RESOURCE_NOT_FOUND"
        assert data["error"]["type"] == "not_found"

    async def test_handler_unauthorized_subclass(self, client):
        resp = await client.get("/raise/unauthorized")
        assert resp.status_code == 401
        data = resp.json()
        assert data["error"]["code"] == "UNIAPI_INVALID_TOKEN"
        assert data["error"]["type"] == "authentication"

    async def test_handler_quota_subclass(self, client):
        resp = await client.get("/raise/quota")
        assert resp.status_code == 402
        data = resp.json()
        assert data["error"]["code"] == "UNIAPI_QUOTA_EXHAUSTED"
        assert data["error"]["type"] == "quota"

    async def test_handler_no_detail_for_non_relay(self, client):
        """Non-RelayException should NOT have top-level detail."""
        resp = await client.get("/raise/app")
        data = resp.json()
        assert "detail" not in data


class TestRelayExceptionHandler:
    """Task 1.3: RelayException produces Phase-A compat format."""

    async def test_relay_handler_returns_compat_format(self, client):
        resp = await client.get("/raise/relay")
        assert resp.status_code == 403
        data = resp.json()
        # Phase A: both detail and error present
        assert "detail" in data
        assert data["detail"] == "Token not allowed"
        assert data["error"]["code"] == "UNIAPI_TOKEN_MODEL_NOT_ALLOWED"
        assert data["error"]["type"] == "authorization"

    async def test_upstream_handler_includes_upstream(self, client):
        resp = await client.get("/raise/upstream")
        assert resp.status_code == 504
        data = resp.json()
        assert data["error"]["code"] == "UPSTREAM_TIMEOUT"
        assert data["error"]["upstream"]["provider"] == "deepseek"
        assert data["error"]["upstream"]["status_code"] == 504
        # Phase A compat
        assert "detail" in data


# ── HTTPException → standard format tests ────────────────────────────────────


class TestHTTPExceptionHandler:
    """Task 1.4: HTTPException is mapped to standard error format."""

    async def test_http_401_maps_to_authentication(self, client):
        resp = await client.get("/raise/http-401")
        assert resp.status_code == 401
        data = resp.json()
        assert data["error"]["code"] == "UNIAPI_INVALID_TOKEN"
        assert data["error"]["type"] == "authentication"

    async def test_http_403_maps_to_authorization(self, client):
        resp = await client.get("/raise/http-403")
        assert resp.status_code == 403
        data = resp.json()
        assert data["error"]["code"] == "UNIAPI_ADMIN_REQUIRED"
        assert data["error"]["type"] == "authorization"

    async def test_http_429_maps_to_rate_limit(self, client):
        resp = await client.get("/raise/http-429")
        assert resp.status_code == 429
        data = resp.json()
        assert data["error"]["code"] == "UNIAPI_RATE_LIMITED"
        assert data["error"]["type"] == "rate_limit"

    async def test_http_500_maps_to_internal(self, client):
        resp = await client.get("/raise/http-500")
        assert resp.status_code == 500
        data = resp.json()
        assert data["error"]["code"] == "UNIAPI_INTERNAL_ERROR"
        assert data["error"]["type"] == "internal"

    async def test_http_exception_message_is_preserved(self, client):
        resp = await client.get("/raise/http-401")
        data = resp.json()
        assert data["error"]["message"] == "Not logged in"

    async def test_http_exception_has_request_id(self, client):
        resp = await client.get("/raise/http-500")
        data = resp.json()
        assert data["error"]["request_id"] == "req_test_handler_123"

    async def test_http_exception_includes_detail_compat(self, client):
        """HTTPException from /v1/* paths gets Phase A compat detail."""
        resp = await client.get("/raise/http-403")
        data = resp.json()
        # HTTPException handler uses RelayException-compatible output
        assert "detail" in data
        assert data["detail"] == "Admin required"

    async def test_no_http_handler_falls_back_to_fastapi_default(self, client_no_http_handler):
        """Without custom handler, HTTPException uses FastAPI defaults."""
        resp = await client_no_http_handler.get("/raise/http-500")
        assert resp.status_code == 500
        data = resp.json()
        # FastAPI default: just {"detail": "..."}
        assert "detail" in data
        # No standard error object
        assert "error" not in data


class TestOpenAIFormatOnV1Paths:
    """/v1/* paths produce OpenAI-compatible error format."""

    async def test_v1_path_relay_returns_openai_format(self, client):
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
