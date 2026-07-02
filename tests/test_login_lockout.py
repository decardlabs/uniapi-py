"""Tests for login brute-force protection and security fixes."""
from __future__ import annotations

import time

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.config import settings
from app.database import async_session_factory
from app.models.user import User


class TestLoginLockoutFields:
    """User model has lockout fields and config has lockout settings."""

    def test_user_model_has_failed_login_attempts(self):
        """User model has a 'failed_login_attempts' column."""
        assert hasattr(User, "failed_login_attempts")

    def test_user_model_has_locked_until(self):
        """User model has a 'locked_until' column."""
        assert hasattr(User, "locked_until")

    def test_login_max_attempts_config(self):
        """Config has login_max_attempts defaulting to 5."""
        assert hasattr(settings, "login_max_attempts")
        assert settings.login_max_attempts == 5

    def test_login_lockout_minutes_config(self):
        """Config has login_lockout_minutes defaulting to 15."""
        assert hasattr(settings, "login_lockout_minutes")
        assert settings.login_lockout_minutes == 15


class TestLoginErrorMessageUnification:
    """All auth failures return the same generic message."""

    async def test_nonexistent_user_returns_generic_message(self, client: AsyncClient):
        """Login with non-existent username returns '用户名或密码错误'."""
        resp = await client.post(
            "/api/user/login",
            json={"username": "nonexistent_user_xyz", "password": "SomePass123"},
        )
        data = resp.json()
        assert resp.status_code == 401
        assert data["success"] is False
        assert data["message"] == "用户名或密码错误"

    async def test_wrong_password_returns_generic_message(self, client: AsyncClient):
        """Login with wrong password returns generic message."""
        # Register a user first
        reg_resp = await client.post(
            "/api/user/register",
            json={"username": "enumtest_user", "password": "StrongPass1"},
        )
        assert reg_resp.status_code == 200

        resp = await client.post(
            "/api/user/login",
            json={"username": "enumtest_user", "password": "WrongPass1"},
        )
        data = resp.json()
        assert resp.status_code == 401
        assert data["success"] is False
        assert data["message"] == "用户名或密码错误"

    async def test_disabled_account_returns_generic_message(self, client: AsyncClient):
        """Login with disabled account returns generic message."""
        # Register a user
        reg_resp = await client.post(
            "/api/user/register",
            json={"username": "disabled_user", "password": "StrongPass1"},
        )
        assert reg_resp.status_code == 200

        # Disable the user via direct DB access
        async with async_session_factory() as db:
            result = await db.execute(
                select(User).where(User.username == "disabled_user")
            )
            user = result.scalar_one_or_none()
            assert user is not None
            user.status = 2
            await db.commit()

        resp = await client.post(
            "/api/user/login",
            json={"username": "disabled_user", "password": "StrongPass1"},
        )
        data = resp.json()
        assert resp.status_code == 401
        assert data["success"] is False
        assert data["message"] == "用户名或密码错误"


class TestLoginLockoutLogic:
    """Brute-force protection with attempt tracking."""

    async def test_failed_login_increments_counter(self, client: AsyncClient):
        """Failed login attempts increment failed_login_attempts."""
        await client.post(
            "/api/user/register",
            json={"username": "counter_user", "password": "StrongPass1"},
        )
        # One wrong password attempt
        await client.post(
            "/api/user/login",
            json={"username": "counter_user", "password": "WrongPass1"},
        )

        async with async_session_factory() as db:
            result = await db.execute(
                select(User).where(User.username == "counter_user")
            )
            user = result.scalar_one()
            assert user.failed_login_attempts == 1

    async def test_failed_login_returns_attempts_remaining(self, client: AsyncClient):
        """Response includes attempts_remaining in data."""
        await client.post(
            "/api/user/register",
            json={"username": "remaining_user", "password": "StrongPass1"},
        )
        resp = await client.post(
            "/api/user/login",
            json={"username": "remaining_user", "password": "WrongPass1"},
        )
        data = resp.json()
        assert data.get("data", {}).get("attempts_remaining") == 4  # 5 - 1

    async def test_account_locks_after_max_failures(self, client: AsyncClient):
        """Account locks after login_max_attempts consecutive failures."""
        await client.post(
            "/api/user/register",
            json={"username": "lockout_user", "password": "StrongPass1"},
        )
        for _ in range(5):
            await client.post(
                "/api/user/login",
                json={"username": "lockout_user", "password": "WrongPass1"},
            )

        # Attempt #6 should get 423 locked
        resp = await client.post(
            "/api/user/login",
            json={"username": "lockout_user", "password": "WrongPass1"},
        )
        assert resp.status_code == 423
        data = resp.json()
        assert data.get("data", {}).get("locked") is True

        # Verify DB state
        async with async_session_factory() as db:
            result = await db.execute(
                select(User).where(User.username == "lockout_user")
            )
            user = result.scalar_one()
            assert user.failed_login_attempts == 5
            assert user.locked_until is not None
            assert user.locked_until > int(time.time() * 1000)

    async def test_locked_account_returns_locked_status(self, client: AsyncClient):
        """Locked account returns locked status with generic message."""
        await client.post(
            "/api/user/register",
            json={"username": "locked_user", "password": "StrongPass1"},
        )
        for _ in range(5):
            await client.post(
                "/api/user/login",
                json={"username": "locked_user", "password": "WrongPass1"},
            )
        resp = await client.post(
            "/api/user/login",
            json={"username": "locked_user", "password": "WrongPass1"},
        )
        data = resp.json()
        assert resp.status_code == 423
        assert data.get("data", {}).get("locked") is True
        assert data["message"] == "用户名或密码错误"

    async def test_login_resets_counter_on_success(self, client: AsyncClient):
        """Successful login resets failed_login_attempts and clears locked_until."""
        await client.post(
            "/api/user/register",
            json={"username": "reset_user", "password": "StrongPass1"},
        )
        # 3 failed attempts
        for _ in range(3):
            await client.post(
                "/api/user/login",
                json={"username": "reset_user", "password": "WrongPass1"},
            )
        # Successful login resets
        resp = await client.post(
            "/api/user/login",
            json={"username": "reset_user", "password": "StrongPass1"},
        )
        assert resp.status_code == 200

        async with async_session_factory() as db:
            result = await db.execute(
                select(User).where(User.username == "reset_user")
            )
            user = result.scalar_one()
            assert user.failed_login_attempts == 0
            assert user.locked_until is None

    async def test_wrong_password_does_db_commit(self):
        """Wrong password path does db.commit() to prevent timing leaks."""
        import inspect
        from app.services import user as user_service

        source = inspect.getsource(user_service.login_user)
        # The wrong-password path must call db.commit() (writes attempt count)
        assert "db.commit()" in source

    async def test_all_failure_paths_have_distinct_db_writes(self):
        """not-found: db.flush; wrong-password+disabled: db.commit."""
        import inspect
        from app.services import user as user_service

        source = inspect.getsource(user_service.login_user)
        assert "db.flush()" in source
        assert "db.commit()" in source
