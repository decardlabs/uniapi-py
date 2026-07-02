"""Tests for verification endpoint security and rate limiting."""
from __future__ import annotations

import time

import pytest
from httpx import AsyncClient

from app.config import settings
from app.services.email import _verification_codes, _email_send_limits, check_email_rate_limit


class TestVerificationEndpointSecurity:
    """P0: Verification endpoint must not leak email registration status."""

    async def test_does_not_reveal_if_email_registered(self, client: AsyncClient):
        """Registered email returns same response as unregistered (no enumeration)."""
        # Register a user with an email
        from app.database import async_session_factory
        from app.models.user import User
        from app.services.auth import hash_password
        from sqlalchemy import select

        async with async_session_factory() as db:
            result = await db.execute(
                select(User).where(User.username == "enum_test_user")
            )
            existing = result.scalar_one_or_none()
            if not existing:
                now = int(time.time() * 1000)
                user = User(
                    username="enum_test_user",
                    password=hash_password("StrongPass1"),
                    display_name="enum_test_user",
                    role=1,
                    status=1,
                    email="enum_test_registered@example.com",
                    balance=2000000,
                    group="default",
                    created_at=now,
                    updated_at=now,
                )
                db.add(user)
                await db.commit()

        # Call verification with the registered email
        resp = await client.post(
            "/api/verification",
            json={"email": "enum_test_registered@example.com"},
        )
        data = resp.json()
        # SMTP not configured → success=False with generic message (not "已注册")
        assert data["success"] is False
        assert "注册" not in data.get("message", ""), (
            "Should not hint that email is registered"
        )

    async def test_does_not_reveal_if_email_not_registered(self, client: AsyncClient):
        """Unregistered email returns same response shape as registered."""
        # Clear any state
        from app.services.email import _verification_codes, _email_send_limits
        _verification_codes.clear()
        _email_send_limits.clear()

        resp = await client.post(
            "/api/verification",
            json={"email": "nonexistent@example.com"},
        )
        data = resp.json()
        # Same result as registered: SMTP not configured
        assert data["success"] is False
        assert "注册" not in data.get("message", "")

    async def test_both_emails_get_identical_response(self, client: AsyncClient):
        """Registered and unregistered emails get the EXACT same response."""
        from app.services.email import _verification_codes, _email_send_limits
        _verification_codes.clear()
        _email_send_limits.clear()

        # First: unregistered
        resp1 = await client.post(
            "/api/verification",
            json={"email": "compare_a@example.com"},
        )

        _verification_codes.clear()
        _email_send_limits.clear()

        # Seed a registered email and call it
        from app.database import async_session_factory
        from app.models.user import User
        from app.services.auth import hash_password
        from sqlalchemy import select

        async with async_session_factory() as db:
            result = await db.execute(
                select(User).where(User.username == "compare_user")
            )
            existing = result.scalar_one_or_none()
            if not existing:
                now = int(time.time() * 1000)
                user = User(
                    username="compare_user",
                    password=hash_password("StrongPass1"),
                    email="compare_b@example.com",
                    role=1,
                    status=1,
                    group="default",
                    created_at=now,
                    updated_at=now,
                )
                db.add(user)
                await db.commit()

        resp2 = await client.post(
            "/api/verification",
            json={"email": "compare_b@example.com"},
        )

        d1, d2 = resp1.json(), resp2.json()
        # Both should be success=False (SMTP not configured)
        # and have the same message
        assert d1["success"] is False
        assert d2["success"] is False
        assert d1["message"] == d2["message"], (
            "Registered and unregistered emails must return identical response"
        )

    async def test_verification_requires_no_auth(self, client: AsyncClient):
        """Verification endpoint is public (no auth needed)."""
        from app.services.email import _verification_codes, _email_send_limits
        _verification_codes.clear()
        _email_send_limits.clear()

        resp = await client.post(
            "/api/verification",
            json={"email": "public@example.com"},
        )
        # Should work without any cookies/auth headers
        assert resp.status_code == 200


class TestVerificationEndpointMethod:
    """P1: Verification endpoint must use POST, not GET."""

    async def test_get_returns_404(self, client: AsyncClient):
        """GET /api/verification should return 404 (no GET route)."""
        resp = await client.get(
            "/api/verification?email=test@example.com",
        )
        assert resp.status_code == 404, (
            f"Expected 404, got {resp.status_code}. "
            "The endpoint should have changed from GET to POST."
        )

    async def test_post_works_with_valid_email(self, client: AsyncClient):
        """POST with valid email returns 200."""
        # Clear any rate limits for this test
        _email_send_limits.clear()
        _verification_codes.clear()

        resp = await client.post(
            "/api/verification",
            json={"email": "valid@example.com"},
        )
        assert resp.status_code == 200

    async def test_post_rejects_invalid_email(self, client: AsyncClient):
        """POST with invalid email format returns 422."""
        resp = await client.post(
            "/api/verification",
            json={"email": "not-an-email"},
        )
        assert resp.status_code == 422, (
            f"Expected 422 for invalid email, got {resp.status_code}"
        )


class TestVerificationRateLimit:
    """P1: Per-email rate limiting for verification code sending."""

    async def test_first_requests_succeed(self, client: AsyncClient):
        """First 3 attempts for the same email all succeed."""
        _email_send_limits.clear()
        _verification_codes.clear()

        email = "ratelimit1@example.com"
        for i in range(3):
            resp = await client.post(
                "/api/verification",
                json={"email": email},
            )
            assert resp.status_code == 200, (
                f"Attempt {i + 1} should succeed, got {resp.status_code}: {resp.text}"
            )

    async def test_exceeding_rate_limit_returns_too_many_requests(self, client: AsyncClient):
        """4th attempt for the same email within the window is rate-limited."""
        _email_send_limits.clear()
        _verification_codes.clear()

        email = "ratelimit2@example.com"
        for i in range(3):
            resp = await client.post(
                "/api/verification",
                json={"email": email},
            )
            assert resp.status_code == 200, f"Attempt {i + 1} should succeed"

        # 4th attempt should be rate limited
        resp = await client.post(
            "/api/verification",
            json={"email": email},
        )
        data = resp.json()
        assert data["success"] is False
        assert "频繁" in data.get("message", "") or "try again later" in data.get("message", "").lower()

    async def test_different_emails_have_independent_limits(self, client: AsyncClient):
        """Rate limiting email A does not affect email B."""
        _email_send_limits.clear()
        _verification_codes.clear()

        # Exhaust email A
        for i in range(3):
            await client.post(
                "/api/verification",
                json={"email": "alimit@example.com"},
            )

        # Email B should still work
        resp = await client.post(
            "/api/verification",
            json={"email": "blimit@example.com"},
        )
        assert resp.status_code == 200, "Different email should not be rate limited"

    async def test_rate_limit_function_directly(self):
        """Direct unit test of check_email_rate_limit function."""
        _email_send_limits.clear()

        # First call: allowed, 3 remaining
        allowed, remaining = check_email_rate_limit("direct@example.com")
        assert allowed is True
        assert remaining == 2  # 3 - 1 (this call counts)

        # Second call
        allowed, remaining = check_email_rate_limit("direct@example.com")
        assert allowed is True
        assert remaining == 1

        # Third call
        allowed, remaining = check_email_rate_limit("direct@example.com")
        assert allowed is True
        assert remaining == 0

        # Fourth call: blocked
        allowed, remaining = check_email_rate_limit("direct@example.com")
        assert allowed is False
        assert remaining == 0


@pytest.mark.usefixtures("_clear_email_state")
class TestEmailBindEndpointExisting:
    """Existing email binding tests — confirm POST change doesn't break them."""

    async def test_bind_get_returns_405_or_not_found(self, client: AsyncClient):
        """GET /api/oauth/email/bind should not work."""
        resp = await client.post(
            "/api/user/login",
            json={"username": "root", "password": "123456"},
        )
        cookies = resp.cookies

        resp = await client.get(
            "/api/oauth/email/bind?email=test@example.com&code=123456",
            cookies=cookies,
        )
        assert resp.status_code in (405, 404), (
            f"Expected 405/404, got {resp.status_code}"
        )

    async def test_bind_post_succeeds_with_valid_code(self, client: AsyncClient):
        """POST /api/oauth/email/bind with valid code and email."""
        resp = await client.post(
            "/api/user/login",
            json={"username": "root", "password": "123456"},
        )
        cookies = resp.cookies

        from app.services.email import _store_code
        _store_code("bind_test@example.com", "123456")

        resp = await client.post(
            "/api/oauth/email/bind",
            json={"email": "bind_test@example.com", "code": "123456"},
            cookies=cookies,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True

    async def test_bind_rejects_invalid_email_format(self, client: AsyncClient):
        """POST /api/oauth/email/bind rejects invalid email."""
        resp = await client.post(
            "/api/user/login",
            json={"username": "root", "password": "123456"},
        )
        cookies = resp.cookies

        resp = await client.post(
            "/api/oauth/email/bind",
            json={"email": "not-an-email", "code": "123456"},
            cookies=cookies,
        )
        assert resp.status_code == 422

    async def test_bind_rejects_wrong_code(self, client: AsyncClient):
        """POST /api/oauth/email/bind rejects wrong code."""
        resp = await client.post(
            "/api/user/login",
            json={"username": "root", "password": "123456"},
        )
        cookies = resp.cookies

        from app.services.email import _store_code
        _store_code("wrong_code_test@example.com", "999999")

        resp = await client.post(
            "/api/oauth/email/bind",
            json={"email": "wrong_code_test@example.com", "code": "000000"},
            cookies=cookies,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False


@pytest.fixture
def _clear_email_state():
    """Clean up in-memory email state after each test."""
    yield
    _verification_codes.clear()
    _email_send_limits.clear()
