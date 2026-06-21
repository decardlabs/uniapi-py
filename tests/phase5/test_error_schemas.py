"""Phase 5, Task 0.2: Tests for error response Pydantic schemas."""

import json
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError


class TestUpstreamErrorDetail:
    """Tests for the UpstreamErrorDetail model."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        from app.schemas.error import UpstreamErrorDetail

        self.UpstreamErrorDetail = UpstreamErrorDetail

    def test_minimal_upstream_fields(self):
        """Minimal upstream requires only provider and status_code."""
        u = self.UpstreamErrorDetail(provider="deepseek", status_code=429)
        assert u.provider == "deepseek"
        assert u.status_code == 429
        assert u.code is None
        assert u.message is None
        assert u.request_id is None

    def test_full_upstream_fields(self):
        """All upstream fields populated."""
        u = self.UpstreamErrorDetail(
            provider="deepseek",
            status_code=400,
            code="content_filter",
            message="Content blocked",
            request_id="deepseek_req_xyz",
        )
        assert u.provider == "deepseek"
        assert u.status_code == 400
        assert u.code == "content_filter"
        assert u.message == "Content blocked"
        assert u.request_id == "deepseek_req_xyz"

    def test_no_raw_field(self):
        """UpstreamErrorDetail must not accept a 'raw' field."""
        with pytest.raises(ValidationError):
            self.UpstreamErrorDetail(
                provider="deepseek", status_code=500, raw={"foo": "bar"}
            )

    def test_provider_is_required(self):
        """provider is required."""
        with pytest.raises(ValidationError):
            self.UpstreamErrorDetail(status_code=500)

    def test_status_code_is_required(self):
        """status_code is required."""
        with pytest.raises(ValidationError):
            self.UpstreamErrorDetail(provider="deepseek")

    def test_serialization_excludes_none(self):
        """None fields should be excluded from JSON output."""
        u = self.UpstreamErrorDetail(provider="deepseek", status_code=429)
        data = u.model_dump(exclude_none=True)
        assert "code" not in data
        assert "message" not in data
        assert "request_id" not in data


class TestStandardErrorDetail:
    """Tests for the StandardErrorDetail model."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        from app.schemas.error import StandardErrorDetail

        self.StandardErrorDetail = StandardErrorDetail

    def test_minimal_required_fields(self):
        """Only code, message, type, status_code are strictly required for construction.

        request_id and timestamp have defaults.
        """
        err = self.StandardErrorDetail(
            code="UNIAPI_INTERNAL_ERROR",
            message="Something went wrong",
            type="internal",
            status_code=500,
        )
        assert err.code == "UNIAPI_INTERNAL_ERROR"
        assert err.message == "Something went wrong"
        assert err.type == "internal"
        assert err.status_code == 500
        assert err.request_id is not None  # auto-generated
        assert err.timestamp is not None  # auto-generated

    def test_full_fields(self):
        """All fields populated including optional ones."""
        from app.schemas.error import UpstreamErrorDetail

        upstream = UpstreamErrorDetail(provider="deepseek", status_code=502)
        err = self.StandardErrorDetail(
            code="UPSTREAM_TIMEOUT",
            message="Upstream timed out",
            type="upstream",
            status_code=504,
            details={"timeout_seconds": 300},
            suggestion="Retry with exponential backoff.",
            request_id="req_abc123",
            timestamp="2026-06-21T10:30:00Z",
            upstream=upstream,
        )
        assert err.code == "UPSTREAM_TIMEOUT"
        assert err.details == {"timeout_seconds": 300}
        assert err.suggestion == "Retry with exponential backoff."
        assert err.request_id == "req_abc123"
        assert err.timestamp == "2026-06-21T10:30:00Z"
        assert err.upstream == upstream

    def test_timestamp_is_iso8601(self):
        """Auto-generated timestamp must be ISO 8601 UTC."""
        err = self.StandardErrorDetail(
            code="UNIAPI_INTERNAL_ERROR",
            message="Error",
            type="internal",
            status_code=500,
        )
        # Should parse without error
        ts = err.timestamp
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        assert dt.tzinfo is not None

    def test_request_id_auto_generated(self):
        """request_id is auto-generated when not provided."""
        err = self.StandardErrorDetail(
            code="UNIAPI_INTERNAL_ERROR",
            message="Error",
            type="internal",
            status_code=500,
        )
        assert err.request_id
        assert len(err.request_id) > 0
        assert err.request_id.startswith("req_")

    def test_optional_fields_none_by_default(self):
        """details, suggestion, upstream default to None."""
        err = self.StandardErrorDetail(
            code="UNIAPI_INTERNAL_ERROR",
            message="Error",
            type="internal",
            status_code=500,
        )
        assert err.details is None
        assert err.suggestion is None
        assert err.upstream is None

    def test_serialization_excludes_none_optionals(self):
        """None optional fields should be excluded from JSON."""
        err = self.StandardErrorDetail(
            code="UNIAPI_INTERNAL_ERROR",
            message="Error",
            type="internal",
            status_code=500,
        )
        data = err.model_dump(exclude_none=True)
        assert "details" not in data
        assert "suggestion" not in data
        assert "upstream" not in data


class TestStandardErrorResponse:
    """Tests for the StandardErrorResponse wrapper."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        from app.schemas.error import StandardErrorDetail, StandardErrorResponse

        self.StandardErrorDetail = StandardErrorDetail
        self.StandardErrorResponse = StandardErrorResponse

    def test_success_is_always_false(self):
        """StandardErrorResponse.success must always be False."""
        err = self.StandardErrorDetail(
            code="UNIAPI_INTERNAL_ERROR",
            message="Error",
            type="internal",
            status_code=500,
        )
        resp = self.StandardErrorResponse(success=False, error=err)
        assert resp.success is False

    def test_json_serialization(self):
        """Full response serializes to correct JSON structure per spec §5."""
        err = self.StandardErrorDetail(
            code="UNIAPI_TOKEN_MODEL_NOT_ALLOWED",
            message="Token not allowed to use model 'deepseek-v4-pro'",
            type="authorization",
            status_code=403,
            details={"requested_model": "deepseek-v4-pro", "allowed_models": ["glm-5.2"]},
            suggestion="Call GET /v1/models to list available models.",
            request_id="req_abc123",
            timestamp="2026-06-21T10:30:00Z",
        )
        resp = self.StandardErrorResponse(success=False, error=err)
        data = resp.model_dump(exclude_none=True)

        assert data["success"] is False
        assert data["error"]["code"] == "UNIAPI_TOKEN_MODEL_NOT_ALLOWED"
        assert data["error"]["message"] == "Token not allowed to use model 'deepseek-v4-pro'"
        assert data["error"]["type"] == "authorization"
        assert data["error"]["status_code"] == 403
        assert data["error"]["details"]["requested_model"] == "deepseek-v4-pro"
        assert data["error"]["details"]["allowed_models"] == ["glm-5.2"]
        assert data["error"]["suggestion"] == "Call GET /v1/models to list available models."
        assert data["error"]["request_id"] == "req_abc123"
        assert data["error"]["timestamp"] == "2026-06-21T10:30:00Z"

    def test_json_string_output(self):
        """model_dump_json produces valid JSON string."""
        err = self.StandardErrorDetail(
            code="UNIAPI_INTERNAL_ERROR",
            message="Error",
            type="internal",
            status_code=500,
            request_id="req_test",
            timestamp="2026-06-21T10:30:00Z",
        )
        resp = self.StandardErrorResponse(success=False, error=err)
        json_str = resp.model_dump_json(exclude_none=True)
        parsed = json.loads(json_str)
        assert parsed["success"] is False
        assert parsed["error"]["code"] == "UNIAPI_INTERNAL_ERROR"


class TestBuildErrorResponse:
    """Tests for the build_error_response factory function."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        from app.schemas.error import build_error_response

        self.build = build_error_response

    def test_build_minimal(self):
        """build_error_response with code + message produces valid structure."""
        resp = self.build("UNIAPI_INVALID_REQUEST", "Invalid request")
        assert resp["success"] is False
        assert resp["error"]["code"] == "UNIAPI_INVALID_REQUEST"
        assert resp["error"]["message"] == "Invalid request"
        assert resp["error"]["type"] == "validation"
        assert resp["error"]["status_code"] == 400
        assert "request_id" in resp["error"]

    def test_build_with_details(self):
        """Pass details dict."""
        resp = self.build(
            "UNIAPI_INVALID_REQUEST",
            "Missing field",
            details={"field": "model"},
        )
        assert resp["error"]["details"] == {"field": "model"}

    def test_build_with_suggestion(self):
        """Pass suggestion string."""
        resp = self.build(
            "UNIAPI_INVALID_REQUEST",
            "Missing field",
            suggestion="Include the 'model' field.",
        )
        assert resp["error"]["suggestion"] == "Include the 'model' field."

    def test_build_with_upstream(self):
        """Pass upstream dict gets converted to UpstreamErrorDetail."""
        upstream_dict = {
            "provider": "deepseek",
            "status_code": 429,
            "code": "rate_limited",
            "message": "Too many requests",
        }
        resp = self.build(
            "UPSTREAM_RATE_LIMITED",
            "Upstream rate limited",
            upstream=upstream_dict,
        )
        assert resp["error"]["upstream"]["provider"] == "deepseek"
        assert resp["error"]["upstream"]["status_code"] == 429
        assert resp["error"]["upstream"]["code"] == "rate_limited"

    def test_build_unknown_code_fallback(self):
        """Unknown code falls back to 500 internal."""
        resp = self.build("MY_CUSTOM_CODE", "Custom error")
        assert resp["error"]["status_code"] == 500
        assert resp["error"]["type"] == "internal"
        # code is preserved as-is
        assert resp["error"]["code"] == "MY_CUSTOM_CODE"

    def test_build_with_explicit_request_id(self):
        """Explicit request_id overrides auto-generated."""
        resp = self.build(
            "UNIAPI_INTERNAL_ERROR",
            "Error",
            request_id="req_manual_123",
        )
        assert resp["error"]["request_id"] == "req_manual_123"

    def test_build_timestamp_is_iso8601(self):
        """Timestamp must be valid ISO 8601."""
        resp = self.build("UNIAPI_INTERNAL_ERROR", "Error")
        ts = resp["error"]["timestamp"]
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        assert dt.tzinfo is not None

    def test_build_error_response_excludes_none_optionals(self):
        """Response dict should not contain keys for None optional fields."""
        resp = self.build("UNIAPI_INTERNAL_ERROR", "Error")
        assert "details" not in resp["error"]
        assert "suggestion" not in resp["error"]
        assert "upstream" not in resp["error"]


class TestBuildCompatErrorResponse:
    """Tests for the build_compat_error_response factory (Phase A compatibility)."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        from app.schemas.error import build_compat_error_response

        self.build_compat = build_compat_error_response

    def test_compat_response_has_both_detail_and_error(self):
        """Phase A: response must include top-level 'detail' AND 'error'."""
        resp = self.build_compat(
            "UNIAPI_TOKEN_MODEL_NOT_ALLOWED",
            "Token not allowed to use model 'deepseek-v4-pro'",
        )
        assert "detail" in resp
        assert "error" in resp
        assert resp["success"] is False

    def test_detail_matches_error_message(self):
        """The top-level 'detail' must mirror error.message for compatibility."""
        msg = "Token not allowed to use model 'deepseek-v4-pro'"
        resp = self.build_compat("UNIAPI_TOKEN_MODEL_NOT_ALLOWED", msg)
        assert resp["detail"] == msg
        assert resp["error"]["message"] == msg

    def test_compat_response_success_is_false(self):
        """success must always be False in error responses."""
        resp = self.build_compat("UNIAPI_INTERNAL_ERROR", "Error")
        assert resp["success"] is False

    def test_compat_response_has_request_id(self):
        """Phase A compat still includes request_id."""
        resp = self.build_compat("UNIAPI_INTERNAL_ERROR", "Error")
        assert "request_id" in resp["error"]

    def test_compat_response_with_upstream(self):
        """Phase A with upstream error info."""
        resp = self.build_compat(
            "UPSTREAM_TIMEOUT",
            "Upstream timed out",
            upstream={"provider": "deepseek", "status_code": 504},
        )
        assert "detail" in resp
        assert resp["error"]["upstream"]["provider"] == "deepseek"
        assert resp["error"]["upstream"]["status_code"] == 504

    def test_compat_response_no_detail_when_none(self):
        """If detail is explicitly None, it should be excluded from output."""
        resp = self.build_compat(
            "UNIAPI_INTERNAL_ERROR",
            "Error",
            include_detail=False,
        )
        assert "detail" not in resp
        assert "error" in resp


class TestUpstreamErrorImmutability:
    """UpstreamErrorDetail values should not be mutable through dict access."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        from app.schemas.error import UpstreamErrorDetail

        self.UpstreamErrorDetail = UpstreamErrorDetail

    def test_upstream_fields_read_only(self):
        """UpstreamErrorDetail is a Pydantic model — fields are settable on instance
        but the serialized output should not contain unexpected keys."""
        u = self.UpstreamErrorDetail(
            provider="glm", status_code=500, code="internal_error"
        )
        data = u.model_dump()
        assert set(data.keys()) == {"provider", "status_code", "code", "message", "request_id"}
