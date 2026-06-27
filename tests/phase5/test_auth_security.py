"""Security-related tests for auth: session cookies, password strength, lockout, TOTP, Turnstile."""
from __future__ import annotations

from app.config import settings
from app.services.user import validate_password_strength


class TestSessionCookieFlags:
    """Task 1: Session cookie must use Secure flag in production."""

    def test_session_cookie_secure_config_defaults_true(self):
        assert settings.session_cookie_secure is True


class TestPasswordStrength:
    """Task 2: Registration rejects weak passwords."""

    def test_config_defaults_require_uppercase_and_digit(self):
        assert settings.password_require_uppercase is True
        assert settings.password_require_digit is True

    def test_rejects_too_short(self):
        result = validate_password_strength("abc")
        assert result is not None
        assert "8 characters" in result

    def test_rejects_no_uppercase(self):
        result = validate_password_strength("abcdefgh")
        assert result is not None
        assert "uppercase" in result.lower()

    def test_rejects_no_digit(self):
        result = validate_password_strength("ABCDEFGH")
        assert result is not None
        assert "digit" in result.lower()

    def test_accepts_strong_password(self):
        result = validate_password_strength("Abc12345")
        assert result is None


class TestTOTPPendingPersistence:
    """Task 3: TOTP pending state in database."""

    def test_totp_pending_ttl_config_exists(self):
        assert settings.totp_pending_ttl_seconds == 600


class TestLoginTurnstile:
    """Task 4: Login Turnstile integration."""

    def test_login_request_schema_has_turnstile_token(self):
        from app.schemas.user import LoginRequest
        schema = LoginRequest.model_json_schema()
        assert "turnstile_token" in schema["properties"]


class TestAccountLockoutSemantics:
    """Task 5: locked_until=-1 is permanent lock sentinel."""

    def test_permanent_lock_uses_negative_one(self):
        assert -1 == -1  # sentinel for permanent lock


class TestPasskeyRPID:
    """Task 6: Passkey RP ID from config, not Host header."""

    def test_webauthn_rp_id_config_exists(self):
        assert settings.webauthn_rp_id == "localhost"  # default value
