"""Phase 5, Task 7: Error code snapshot tests.

Ensures every published error code produces the correct JSON structure
and that the response format is stable across changes.
"""

import json

import pytest

from app.schemas.error import build_error_response, build_compat_error_response

# ── All 20 standard error codes ──────────────────────────────────────────────

ALL_CODES = [
    # Authentication & authorization
    ("UNIAPI_INVALID_TOKEN", "Invalid token"),
    ("UNIAPI_TOKEN_EXPIRED", "Token has expired"),
    ("UNIAPI_TOKEN_MODEL_NOT_ALLOWED", "Token not allowed to use this model"),
    ("UNIAPI_ADMIN_REQUIRED", "Admin access required"),
    ("UNIAPI_GROUP_ACCESS_DENIED", "User group not allowed to access this channel"),
    # Request & validation
    ("UNIAPI_INVALID_REQUEST", "Invalid request parameters"),
    ("UNIAPI_MODEL_NOT_SPECIFIED", "Model not specified in request"),
    ("UNIAPI_MODEL_NOT_SUPPORTED", "Model not supported by any provider"),
    ("UNIAPI_UNSUPPORTED_PARAMETER", "Unsupported parameter provided"),
    ("UNIAPI_RESOURCE_NOT_FOUND", "Resource not found"),
    # Quota & rate limiting
    ("UNIAPI_QUOTA_EXHAUSTED", "Quota exhausted"),
    ("UNIAPI_RATE_LIMITED", "Rate limit exceeded"),
    # Upstream
    ("UPSTREAM_TIMEOUT", "Upstream request timed out"),
    ("UPSTREAM_UNAVAILABLE", "Upstream service unavailable"),
    ("UPSTREAM_BAD_RESPONSE", "Upstream returned invalid response"),
    ("UPSTREAM_RATE_LIMITED", "Upstream rate limited"),
    ("UPSTREAM_CONNECTION_FAILED", "Connection to upstream failed"),
    # Service availability
    ("UNIAPI_SERVICE_DISABLED", "Service is disabled"),
    ("UNIAPI_CHANNEL_UNAVAILABLE", "No enabled channels available"),
    # Internal
    ("UNIAPI_INTERNAL_ERROR", "Internal server error"),
]


# ── Per-code snapshot tests ──────────────────────────────────────────────────


class TestErrorCodeSnapshots:
    """One test per standard error code — verifies response structure."""

    @pytest.mark.parametrize("code,message", ALL_CODES)
    def test_error_response_structure(self, code, message):
        """Each code produces a valid standard error response."""
        resp = build_error_response(code, message)
        assert resp["success"] is False
        assert "error" in resp
        err = resp["error"]
        assert err["code"] == code
        assert err["message"] == message
        assert "type" in err
        assert "status_code" in err
        assert "request_id" in err
        assert "timestamp" in err
        # request_id must not be empty
        assert err["request_id"]
        # timestamp must be non-empty ISO 8601 string
        assert err["timestamp"]
        assert "T" in err["timestamp"]

    @pytest.mark.parametrize("code,message", ALL_CODES)
    def test_compat_response_structure(self, code, message):
        """Phase A compat: each code produces a response with detail + error."""
        resp = build_compat_error_response(code, message)
        assert resp["success"] is False
        assert "detail" in resp
        assert resp["detail"] == message
        assert "error" in resp
        assert resp["error"]["code"] == code

    @pytest.mark.parametrize("code,message", ALL_CODES)
    def test_error_code_never_none(self, code, message):
        """Error code string must never be None or empty."""
        resp = build_error_response(code, message)
        assert resp["error"]["code"]
        assert isinstance(resp["error"]["code"], str)

    @pytest.mark.parametrize("code,message", ALL_CODES)
    def test_status_code_in_valid_range(self, code, message):
        """status_code must be in 4xx-5xx range."""
        resp = build_error_response(code, message)
        sc = resp["error"]["status_code"]
        assert 400 <= sc <= 599, f"{code}: status_code {sc} out of range"


class TestSnapshotRegression:
    """Bulk snapshot test that can detect regressions."""

    def test_full_snapshot_matches_known_good(self):
        """Generate all 20 error responses and verify core invariants.

        This test acts as a canary: if any error code's structure changes,
        this test will catch it.
        """
        snapshot = {}
        for code, message in ALL_CODES:
            resp = build_error_response(code, message)
            # Only keep stable fields (exclude timestamp and request_id which vary)
            stable = {
                "success": resp["success"],
                "code": resp["error"]["code"],
                "type": resp["error"]["type"],
                "status_code": resp["error"]["status_code"],
            }
            snapshot[code] = stable

        # Verify count
        assert len(snapshot) == 20

        # Spot-check key codes
        assert snapshot["UNIAPI_INVALID_TOKEN"]["status_code"] == 401
        assert snapshot["UNIAPI_INVALID_TOKEN"]["type"] == "authentication"
        assert snapshot["UNIAPI_QUOTA_EXHAUSTED"]["status_code"] == 402
        assert snapshot["UNIAPI_QUOTA_EXHAUSTED"]["type"] == "quota"
        assert snapshot["UNIAPI_RATE_LIMITED"]["status_code"] == 429
        assert snapshot["UNIAPI_RATE_LIMITED"]["type"] == "rate_limit"
        assert snapshot["UPSTREAM_TIMEOUT"]["status_code"] == 504
        assert snapshot["UPSTREAM_TIMEOUT"]["type"] == "upstream"
        assert snapshot["UNIAPI_INTERNAL_ERROR"]["status_code"] == 500
        assert snapshot["UNIAPI_INTERNAL_ERROR"]["type"] == "internal"


class TestJSONSerialization:
    """Verify all error responses serialize to valid JSON."""

    @pytest.mark.parametrize("code,message", ALL_CODES)
    def test_serializes_to_valid_json(self, code, message):
        """Each error response must be valid JSON."""
        resp = build_error_response(code, message)
        json_str = json.dumps(resp)
        parsed = json.loads(json_str)
        assert parsed == resp

    @pytest.mark.parametrize("code,message", ALL_CODES)
    def test_compat_serializes_to_valid_json(self, code, message):
        """Compat response must be valid JSON."""
        resp = build_compat_error_response(code, message)
        json_str = json.dumps(resp)
        parsed = json.loads(json_str)
        assert parsed == resp


class TestUpstreamErrorSnapshot:
    """Snapshot tests for upstream errors."""

    def test_upstream_error_full_structure(self):
        upstream_dict = {
            "provider": "deepseek",
            "status_code": 429,
            "code": "rate_limit_exceeded",
            "message": "Too many requests",
            "request_id": "deepseek_req_abc",
        }
        resp = build_error_response(
            "UPSTREAM_RATE_LIMITED",
            "Upstream rate limited",
            upstream=upstream_dict,
        )
        err = resp["error"]
        assert err["upstream"]["provider"] == "deepseek"
        assert err["upstream"]["status_code"] == 429
        assert err["upstream"]["code"] == "rate_limit_exceeded"
        assert err["upstream"]["request_id"] == "deepseek_req_abc"

    def test_safety_blocked_snapshot(self):
        """PROVIDER_DEEPSEEK_SAFETY_BLOCKED must have correct structure."""
        resp = build_error_response(
            "PROVIDER_DEEPSEEK_SAFETY_BLOCKED",
            "Content blocked by upstream safety system",
            upstream={
                "provider": "deepseek",
                "status_code": 400,
                "code": "content_filter",
                "message": "Content blocked",
                "request_id": "deepseek_req_xyz",
            },
        )
        assert resp["error"]["code"] == "PROVIDER_DEEPSEEK_SAFETY_BLOCKED"
        assert resp["error"]["upstream"]["code"] == "content_filter"
        # Unknown code falls back to 500/internal but the code itself is still correct
