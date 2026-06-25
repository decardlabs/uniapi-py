"""Test that TOTP confirm/disable endpoints have rate limiting.

TOTP code space is only 1,000,000 with 3 valid codes per window.
Without rate limiting, brute force is feasible within hours.
"""
from __future__ import annotations

import time
from unittest.mock import patch

import pytest


class TestTOTPRateLimit:
    """TOTP verification endpoints must have rate limiting."""

    def test_functions_exist(self):
        """Rate limit helper functions must exist in totp module."""
        from app.routers.api.totp import (
            TOTP_MAX_ATTEMPTS,
            _check_totp_rate_limit,
            _record_totp_failure,
            _reset_totp_failures,
            totp_confirm,
            totp_disable,
        )

        assert TOTP_MAX_ATTEMPTS == 5
        assert _check_totp_rate_limit is not None
        assert _record_totp_failure is not None
        assert _reset_totp_failures is not None
        assert totp_confirm is not None
        assert totp_disable is not None

    def test_check_allows_first_attempt(self):
        from app.routers.api.totp import _check_totp_rate_limit, _reset_totp_failures

        _reset_totp_failures(999)
        blocked, msg = _check_totp_rate_limit(999)
        assert not blocked
        assert msg == ""

    def test_block_after_max_attempts(self):
        from app.routers.api.totp import (
            TOTP_MAX_ATTEMPTS,
            _check_totp_rate_limit,
            _record_totp_failure,
            _reset_totp_failures,
        )

        _reset_totp_failures(998)
        for _ in range(TOTP_MAX_ATTEMPTS):
            _record_totp_failure(998)

        blocked, msg = _check_totp_rate_limit(998)
        assert blocked
        assert "过多" in msg

    def test_reset_after_success(self):
        from app.routers.api.totp import (
            _check_totp_rate_limit,
            _record_totp_failure,
            _reset_totp_failures,
        )

        _reset_totp_failures(997)
        for _ in range(5):
            _record_totp_failure(997)

        _reset_totp_failures(997)
        blocked, _ = _check_totp_rate_limit(997)
        assert not blocked, "Counter should be reset after success"

    def test_window_expiry(self):
        """After the time window expires, attempts should reset."""
        from app.routers.api.totp import (
            TOTP_WINDOW_MS,
            _check_totp_rate_limit,
            _record_totp_failure,
            _reset_totp_failures,
        )

        _reset_totp_failures(996)
        for _ in range(5):
            _record_totp_failure(996)

        # Mock time to be after the window expires
        future = int(time.time() * 1000) + TOTP_WINDOW_MS + 1000
        with patch("app.routers.api.totp.time") as mock_time:
            mock_time.time.return_value = future / 1000

            blocked, _ = _check_totp_rate_limit(996)
            assert not blocked, "Window expired, should reset"
