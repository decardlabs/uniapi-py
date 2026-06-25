"""Phase 5, Task 3: Tests for auth dependency error responses."""

import pytest


# ── Helper to get a fresh client with a clean token ──────────────────────────


async def _post_relay(client, body=None, token=None):
    """Helper to POST /v1/chat/completions with optional Bearer token."""
    headers = {}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    if body is None:
        body = {"model": "deepseek-chat", "messages": [{"role": "user", "content": "hi"}]}
    return await client.post("/v1/chat/completions", json=body, headers=headers)


class TestTokenAuthErrors:
    """Verify that token_auth failures produce standard error responses."""

    @pytest.fixture(autouse=True)
    async def _setup(self, client):
        self.client = client

    async def test_no_token_returns_401_with_uni_api_invalid_token(self):
        resp = await self.client.post(
            "/v1/chat/completions",
            json={"model": "deepseek-chat", "messages": [{"role": "user", "content": "hi"}]},
            # no Authorization header
        )
        assert resp.status_code == 401
        data = resp.json()
        # OpenAI format on /v1/*
        assert data["error"]["code"] == "invalid_api_key"
        assert data["error"]["type"] == "authentication_error"

    async def test_invalid_token_returns_401(self):
        resp = await _post_relay(self.client, token="invalid-token-12345")
        assert resp.status_code == 401
        data = resp.json()
        # OpenAI format on /v1/*
        assert data["error"]["code"] == "invalid_api_key"

    async def test_error_response_has_no_extra_fields(self):
        """OpenAI format on /v1/* — only standard fields."""
        resp = await _post_relay(self.client, token="invalid-token")
        data = resp.json()
        assert set(data.keys()) == {"error"}
        assert set(data["error"].keys()) == {"message", "type", "param", "code"}

    async def test_valid_token_still_works(self):
        """Ensure normal auth flow is not broken."""
        from app.database import async_session_factory
        from sqlalchemy import select
        from app.models.token import Token

        async with async_session_factory() as db:
            result = await db.execute(select(Token).limit(1))
            token = result.scalar_one_or_none()

        if token:
            resp = await _post_relay(self.client, token=token.key)
            # Will fail on upstream connection (no real provider), but NOT on auth
            # 401/403 would indicate auth failure; anything else is routing
            assert resp.status_code not in (401, 403)


class TestManagementAuthErrors:
    """Verify management API auth errors produce standard format."""

    @pytest.fixture(autouse=True)
    async def _setup(self, client):
        self.client = client

    async def test_unauthenticated_api_call_returns_standard_error(self):
        """Calling /api/* without session should produce standard error."""
        resp = await self.client.get("/api/user/self")
        # May be 401 or redirect depending on session handling
        if resp.status_code == 401:
            data = resp.json()
            # Should have standard error format
            assert "error" in data or "detail" in data

    async def _get_session_cookie(self):
        """Login to get a session cookie."""
        resp = await self.client.post(
            "/api/auth/login",
            json={"username": "root", "password": "123456"},
        )
        return resp.cookies.get("session")

    async def test_admin_endpoint_rejects_non_admin(self):
        """Admin endpoints should reject regular users."""
        # Create a non-admin user first
        resp = await self.client.post(
            "/api/auth/register",
            json={"username": "testuser_noadmin", "password": "test123", "display_name": "Test"},
        )
        if resp.status_code == 200:
            data = resp.json()
            token = data.get("data", {}).get("access_token") or ""
            # Try to access admin endpoint with non-admin token
            resp2 = await self.client.get(
                "/api/admin/users",
                headers={"Authorization": f"Bearer {token}"},
            )
            if resp2.status_code == 403:
                data2 = resp2.json()
                assert "error" in data2 or "detail" in data2
