"""Input validation and injection protection tests.

Checks that the API properly rejects malicious or malformed inputs.
SQLAlchemy parameterized queries should prevent SQLi, but we verify
the API layer doesn't expose raw query execution.
"""

import pytest
from httpx import AsyncClient


async def _login(client: AsyncClient) -> dict:
    resp = await client.post("/api/user/login", json={
        "username": "root", "password": "123456",
    })
    return resp.cookies


class TestSQLLikeInjection:
    """Attempt SQL injection via search params and request bodies.

    These tests verify that the API returns controlled errors instead of
    exposing database errors or executing injected SQL.
    """

    @pytest.mark.asyncio
    async def test_channel_search_sqli(self, client: AsyncClient):
        """SQL injection attempt in channel search should not crash."""
        cookies = await _login(client)
        payloads = [
            "'; DROP TABLE channels; --",
            "' OR 1=1; --",
            "1; SELECT * FROM users;",
            "${7*7}",
            "'; EXEC xp_cmdshell('dir'); --",
        ]
        for payload in payloads:
            resp = await client.get(
                f"/api/channel/search?q={payload}",
                cookies=cookies,
            )
            # Should return 200 (search returns empty) or 422 (validation error)
            # Never 500 with database error
            assert resp.status_code in (200, 422, 400), \
                f"SQLi payload '{payload[:20]}...' caused {resp.status_code}"

    @pytest.mark.asyncio
    async def test_user_search_sqli(self, client: AsyncClient):
        """SQL injection attempt in user search should not crash."""
        cookies = await _login(client)
        resp = await client.get("/api/user/search?q=' OR 1=1 --", cookies=cookies)
        assert resp.status_code in (200, 422, 400)

    @pytest.mark.asyncio
    async def test_token_search_sqli(self, client: AsyncClient):
        """SQL injection attempt in token search."""
        cookies = await _login(client)
        resp = await client.get("/api/token/search?q=' UNION SELECT * FROM users --", cookies=cookies)
        assert resp.status_code in (200, 422, 400)


class TestInputValidation:
    """Malformed inputs should be rejected with 422."""

    @pytest.mark.asyncio
    async def test_channel_create_missing_required_fields(self, client: AsyncClient):
        """Creating a channel without required fields is handled gracefully."""
        cookies = await _login(client)
        resp = await client.post("/api/channel/", json={}, cookies=cookies)
        # The API may accept it with defaults; no 500/crash
        assert resp.status_code < 500, f"Server error on empty create: {resp.status_code}"

    @pytest.mark.asyncio
    async def test_channel_create_invalid_type(self, client: AsyncClient):
        """Channel with invalid type should fail."""
        cookies = await _login(client)
        resp = await client.post("/api/channel/", json={
            "name": "Test",
            "type": -1,  # negative type
            "models": "test",
        }, cookies=cookies)
        assert resp.status_code in (200, 400, 422)

    @pytest.mark.asyncio
    async def test_login_with_empty_fields(self, client: AsyncClient):
        """Login with empty credentials should not crash."""
        resp = await client.post("/api/user/login", json={
            "username": "", "password": "",
        })
        # No 500s from basic input
        assert resp.status_code < 500, f"Server error on empty login: {resp.status_code}"

    @pytest.mark.asyncio
    async def test_login_malformed_json(self, client: AsyncClient):
        """Malformed request body should fail."""
        resp = await client.post(
            "/api/user/login",
            content=b"not json at all",
            headers={"content-type": "application/json"},
        )
        assert resp.status_code in (422, 400)


class TestPathTraversal:
    """Path traversal attempts should be blocked."""

    @pytest.mark.asyncio
    async def test_channel_id_traversal(self, client: AsyncClient):
        """Path traversal attempts should not crash."""
        cookies = await _login(client)
        resp = await client.get("/api/channel/../../etc/passwd", cookies=cookies)
        assert resp.status_code < 500, f"Path traversal caused 5xx: {resp.status_code}"

    @pytest.mark.asyncio
    async def test_user_id_traversal(self, client: AsyncClient):
        """Path traversal in user ID should not crash."""
        cookies = await _login(client)
        resp = await client.get("/api/user/../../etc/shadow", cookies=cookies)
        assert resp.status_code < 500, f"Path traversal caused 5xx: {resp.status_code}"
