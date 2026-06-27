"""Phase 5, Task 0.1: Tests for UniAPI error code constants."""

import pytest

# ── Error code list: the 20 standard codes from the spec §12 ──

ALL_CODES = [
    # Authentication & authorization
    "UNIAPI_INVALID_TOKEN",
    "UNIAPI_TOKEN_EXPIRED",
    "UNIAPI_TOKEN_MODEL_NOT_ALLOWED",
    "UNIAPI_ADMIN_REQUIRED",
    "UNIAPI_GROUP_ACCESS_DENIED",
    # Request & validation
    "UNIAPI_INVALID_REQUEST",
    "UNIAPI_MODEL_NOT_SPECIFIED",
    "UNIAPI_MODEL_NOT_SUPPORTED",
    "UNIAPI_UNSUPPORTED_PARAMETER",
    "UNIAPI_RESOURCE_NOT_FOUND",
    # Quota & rate limiting
    "UNIAPI_QUOTA_EXHAUSTED",
    "UNIAPI_RATE_LIMITED",
    # Upstream
    "UPSTREAM_TIMEOUT",
    "UPSTREAM_UNAVAILABLE",
    "UPSTREAM_BAD_RESPONSE",
    "UPSTREAM_RATE_LIMITED",
    "UPSTREAM_CONNECTION_FAILED",
    # Service availability
    "UNIAPI_SERVICE_DISABLED",
    "UNIAPI_CHANNEL_UNAVAILABLE",
    # Internal
    "UNIAPI_INTERNAL_ERROR",
]


class TestErrorCodeConstants:
    """Verify the error code constant definitions."""

    def test_all_codes_have_unique_values(self):
        """Each error code string must be unique."""
        assert len(ALL_CODES) == len(set(ALL_CODES)), (
            f"Duplicate codes found: {len(ALL_CODES)} total vs {len(set(ALL_CODES))} unique"
        )

    def test_code_count_matches_spec(self):
        """The spec §12 defines exactly 20 standard codes."""
        assert len(ALL_CODES) == 20, f"Expected 20 codes, got {len(ALL_CODES)}"

    def test_code_naming_prefix(self):
        """Every code must start with UNIAPI_ / UPSTREAM_ / PROVIDER_."""
        for code in ALL_CODES:
            assert code.startswith("UNIAPI_") or code.startswith("UPSTREAM_") or code.startswith("PROVIDER_"), (
                f"Code '{code}' does not use a valid prefix (UNIAPI_ / UPSTREAM_ / PROVIDER_)"
            )

    def test_code_no_lowercase(self):
        """Codes must be UPPER_SNAKE_CASE (no lowercase letters)."""
        for code in ALL_CODES:
            assert code == code.upper(), f"Code '{code}' contains lowercase characters"

    def test_upstream_codes_use_upstream_prefix(self):
        """Upstream-related errors must use the UPSTREAM_ prefix."""
        upstream_codes = [
            "UPSTREAM_TIMEOUT",
            "UPSTREAM_UNAVAILABLE",
            "UPSTREAM_BAD_RESPONSE",
            "UPSTREAM_RATE_LIMITED",
            "UPSTREAM_CONNECTION_FAILED",
        ]
        for code in upstream_codes:
            assert code.startswith("UPSTREAM_"), f"'{code}' should start with UPSTREAM_"

    def test_gateway_codes_use_uniapi_prefix(self):
        """Gateway business logic errors must use the UNIAPI_ prefix."""
        uniapi_codes = [
            c for c in ALL_CODES if not c.startswith("UPSTREAM_") and not c.startswith("PROVIDER_")
        ]
        for code in uniapi_codes:
            assert code.startswith("UNIAPI_"), f"'{code}' should start with UNIAPI_"


class TestErrorTypeConstants:
    """Verify the error type enum values."""

    ALL_TYPES = [
        "authentication",
        "authorization",
        "validation",
        "quota",
        "rate_limit",
        "upstream",
        "internal",
        "not_found",
    ]

    def test_error_type_count(self):
        """There should be exactly 8 error types per spec §5.2."""
        assert len(self.ALL_TYPES) == 8

    def test_error_types_are_lowercase(self):
        """Error types use lower_snake_case."""
        for t in self.ALL_TYPES:
            assert t == t.lower(), f"Type '{t}' should be lowercase"
            assert " " not in t, f"Type '{t}' should not contain spaces"


class TestErrorCodeMapping:
    """Verify code → (status_code, type) mapping."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        from app.error_codes import ERROR_CODE_MAP, ErrorType

        self.ERROR_CODE_MAP = ERROR_CODE_MAP
        self.ErrorType = ErrorType

    def test_get_error_meta_known_code(self):
        """Known codes must return a valid (status_code, type) tuple."""
        from app.error_codes import get_error_meta

        for code in ALL_CODES:
            status, etype = get_error_meta(code)
            assert isinstance(status, int), f"status for '{code}' should be int, got {type(status)}"
            assert 400 <= status <= 599, f"status for '{code}' should be in 4xx-5xx range, got {status}"
            assert isinstance(etype, str), f"type for '{code}' should be str"

    def test_get_error_meta_unknown_code(self):
        """Unknown codes should fallback to 500 + internal."""
        from app.error_codes import get_error_meta

        status, etype = get_error_meta("NONEXISTENT_CODE_XYZ")
        assert status == 500
        assert etype == "internal"

    def test_auth_codes_have_4xx_status(self):
        """Authentication/authorization errors use 401/403."""
        from app.error_codes import get_error_meta

        auth_codes = [
            "UNIAPI_INVALID_TOKEN",
            "UNIAPI_TOKEN_EXPIRED",
            "UNIAPI_TOKEN_MODEL_NOT_ALLOWED",
            "UNIAPI_ADMIN_REQUIRED",
            "UNIAPI_GROUP_ACCESS_DENIED",
        ]
        for code in auth_codes:
            status, _ = get_error_meta(code)
            assert status in (401, 403), f"'{code}' should be 401 or 403, got {status}"

    def test_upstream_codes_have_valid_status(self):
        """Upstream errors use 502/503/504, except UPSTREAM_RATE_LIMITED which mirrors upstream 429."""
        from app.error_codes import get_error_meta

        upstream_codes = {
            "UPSTREAM_TIMEOUT": 504,
            "UPSTREAM_UNAVAILABLE": 503,
            "UPSTREAM_BAD_RESPONSE": 502,
            "UPSTREAM_RATE_LIMITED": 429,  # upstream 429 → our 429
            "UPSTREAM_CONNECTION_FAILED": 502,
        }
        for code, expected_status in upstream_codes.items():
            status, _ = get_error_meta(code)
            assert status == expected_status, f"'{code}' should be {expected_status}, got {status}"

    def test_quota_code_uses_402(self):
        """Quota exhausted must use 402 Payment Required."""
        from app.error_codes import get_error_meta

        status, _ = get_error_meta("UNIAPI_QUOTA_EXHAUSTED")
        assert status == 402, f"UNIAPI_QUOTA_EXHAUSTED should be 402, got {status}"

    def test_rate_limit_code_uses_429(self):
        """Rate limited must use 429 Too Many Requests."""
        from app.error_codes import get_error_meta

        status, _ = get_error_meta("UNIAPI_RATE_LIMITED")
        assert status == 429, f"UNIAPI_RATE_LIMITED should be 429, got {status}"

    def test_validation_codes_have_type_validation(self):
        """Validation errors must have type='validation'."""
        from app.error_codes import get_error_meta

        val_codes = [
            "UNIAPI_INVALID_REQUEST",
            "UNIAPI_MODEL_NOT_SPECIFIED",
            "UNIAPI_MODEL_NOT_SUPPORTED",
            "UNIAPI_UNSUPPORTED_PARAMETER",
        ]
        for code in val_codes:
            _, etype = get_error_meta(code)
            assert etype == "validation", f"'{code}' type should be 'validation', got '{etype}'"

    def test_map_contains_all_20_codes(self):
        """ERROR_CODE_MAP must contain entries for all 20 standard codes."""
        for code in ALL_CODES:
            assert code in self.ERROR_CODE_MAP, f"'{code}' missing from ERROR_CODE_MAP"
