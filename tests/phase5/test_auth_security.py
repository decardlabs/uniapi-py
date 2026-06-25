"""Security-related tests for auth: session cookies, password strength, lockout."""
from __future__ import annotations

import pytest

from app.config import settings


class TestSessionCookieFlags:
    """Task 1: Session cookie must use Secure flag in production."""

    def test_session_cookie_secure_config_defaults_true(self):
        """The session_cookie_secure setting defaults to True."""
        assert settings.session_cookie_secure is True
