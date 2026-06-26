"""RBAC (Role-Based Access Control) penetration tests.

Verifies that users with insufficient privileges cannot access
admin-level API endpoints.
"""

import pytest
from httpx import AsyncClient


async def _login(client: AsyncClient, username: str = "root", password: str = "123456") -> dict:
    resp = await client.post("/api/user/login", json={
        "username": username, "password": password,
    })
    return resp.cookies


async def _register_user(client: AsyncClient, username: str) -> dict | None:
    resp = await client.post("/api/user/register", json={
        "username": username,
        "password": "TestPass123!",
        "display_name": username,
        "email": f"{username}@test.local",
    })
    if resp.status_code == 200:
        return resp.cookies
    return None


# ── Admin-only endpoints that non-admin users should NOT access ──────────

# Endpoints that require admin (role >= 10) — regular users should be blocked
# Note: POST /api/token/ is user-accessible (own tokens), GET cache-analytics
# is at a different path; these are tested separately.
ADMIN_ENDPOINTS = [
    ("GET", "/api/channel/"),
    ("POST", "/api/channel/"),
    ("GET", "/api/user/search?q=root"),
    ("GET", "/api/option/"),
    ("GET", "/api/mcp_servers/"),
    ("POST", "/api/mcp_servers/"),
]


class TestRBAC:
    """Low-privilege user should be blocked from admin endpoints."""

    @pytest.fixture(scope="function")
    async def user_cookies(self, client: AsyncClient):
        """Create a regular user and return session cookies."""
        cookies = await _register_user(client, "rbac_test_user")
        if cookies is None:
            # User may already exist — try login
            cookies = await _login(client, "rbac_test_user", "TestPass123!")
        return cookies

    @pytest.mark.asyncio
    @pytest.mark.parametrize("method,path", ADMIN_ENDPOINTS)
    async def test_non_admin_cannot_access_admin_endpoints(
        self, client: AsyncClient, user_cookies: dict, method: str, path: str
    ):
        if user_cookies is None:
            pytest.skip("Could not create user")

        if method == "GET":
            resp = await client.get(path, cookies=user_cookies)
        elif method == "POST":
            resp = await client.post(path, json={}, cookies=user_cookies)
        else:
            pytest.skip(f"Unsupported method {method}")

        assert resp.status_code in (401, 403), (
            f"Non-admin user got {resp.status_code} on {method} {path}, expected 401/403"
        )

    @pytest.mark.asyncio
    async def test_admin_can_access_admin_endpoints(self, client: AsyncClient):
        """Admin user (root) should get 200 on admin endpoints."""
        cookies = await _login(client)
        for method, path in ADMIN_ENDPOINTS[:3]:  # sample a few
            if method == "GET":
                resp = await client.get(path, cookies=cookies)
            else:
                resp = await client.post(path, json={}, cookies=cookies)
            assert resp.status_code != 401, f"Admin got 401 on {path}"
            assert resp.status_code != 403, f"Admin got 403 on {path}"


class TestSelfUserIsolation:
    """Users should only be able to modify their own data."""

    @pytest.mark.asyncio
    async def test_user_cannot_delete_other_user(self, client: AsyncClient):
        """A regular user cannot delete another user's account."""
        cookies_user = await _register_user(client, "self_test_user")
        if cookies_user is None:
            cookies_user = await _login(client, "self_test_user", "TestPass123!")

        # Try to delete user id 1 (root) — should fail
        resp = await client.delete("/api/user/1", cookies=cookies_user)
        assert resp.status_code in (401, 403, 404), f"Got {resp.status_code}"

    @pytest.mark.asyncio
    async def test_user_cannot_modify_other_user(self, client: AsyncClient):
        """A regular user cannot update another user's data."""
        cookies_user = await _login(client, "self_test_user", "TestPass123!")

        resp = await client.put("/api/user/1", json={
            "display_name": "hacked",
        }, cookies=cookies_user)
        assert resp.status_code in (401, 403, 404, 405), f"Got {resp.status_code}, text: {resp.text()[:100]}"
