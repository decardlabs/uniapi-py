"""Tests for email binding endpoint (POST /api/oauth/email/bind)."""
import pytest
from httpx import AsyncClient

from app.services.email import verify_code, _verification_codes


async def _login(client: AsyncClient) -> dict:
    resp = await client.post("/api/user/login", json={
        "username": "root", "password": "123456",
    })
    return resp.cookies


class TestEmailBindEndpoint:
    """Email bind endpoint must use POST and include email validation."""

    async def test_bind_get_returns_405_or_not_found(self, client):
        """GET /api/oauth/email/bind should not work anymore (now POST)."""
        cookies = await _login(client)
        resp = await client.get(
            "/api/oauth/email/bind?email=test@example.com&code=123456",
            cookies=cookies,
        )
        # Should be 405 Method Not Allowed or 404
        assert resp.status_code in (405, 404), f"Expected 405/404, got {resp.status_code}"

    async def test_bind_post_succeeds_with_valid_code(self, client):
        """POST /api/oauth/email/bind should work with valid code and email."""
        cookies = await _login(client)

        # Manually store a verification code (bypass SMTP)
        from app.services.email import _store_code
        _store_code("test@example.com", "123456")

        resp = await client.post(
            "/api/oauth/email/bind",
            json={"email": "test@example.com", "code": "123456"},
            cookies=cookies,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True

    async def test_bind_rejects_invalid_email_format(self, client):
        """POST /api/oauth/email/bind should reject invalid email formats."""
        cookies = await _login(client)
        resp = await client.post(
            "/api/oauth/email/bind",
            json={"email": "not-an-email", "code": "123456"},
            cookies=cookies,
        )
        assert resp.status_code == 422, f"Expected 422, got {resp.status_code}"

    async def test_bind_rejects_wrong_code(self, client):
        """POST /api/oauth/email/bind should reject wrong codes."""
        cookies = await _login(client)

        from app.services.email import _store_code
        _store_code("wrong@example.com", "999999")

        resp = await client.post(
            "/api/oauth/email/bind",
            json={"email": "wrong@example.com", "code": "000000"},
            cookies=cookies,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
