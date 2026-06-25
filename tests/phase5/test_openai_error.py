"""Tests for app/schemas/openai_error.py — OpenAI-compatible error response."""

import pytest
from app.schemas.openai_error import (
    OPENAI_ERROR_MAP,
    get_openai_error_meta,
    build_openai_error_response,
)


class TestGetOpenAIErrorMeta:
    """get_openai_error_meta maps UniAPI codes to OpenAI format."""

    def test_model_not_allowed_maps_to_404_model_not_found(self):
        status, type_, code = get_openai_error_meta("UNIAPI_TOKEN_MODEL_NOT_ALLOWED")
        assert status == 404
        assert type_ == "invalid_request_error"
        assert code == "model_not_found"

    def test_invalid_token_maps_to_401_invalid_api_key(self):
        status, type_, code = get_openai_error_meta("UNIAPI_INVALID_TOKEN")
        assert status == 401
        assert type_ == "authentication_error"
        assert code == "invalid_api_key"

    def test_quota_exhausted_maps_to_429_insufficient_quota(self):
        status, type_, code = get_openai_error_meta("UNIAPI_QUOTA_EXHAUSTED")
        assert status == 429
        assert type_ == "insufficient_quota"
        assert code == "insufficient_quota"

    def test_model_not_supported_maps_to_404_model_not_found(self):
        status, type_, code = get_openai_error_meta("UNIAPI_MODEL_NOT_SUPPORTED")
        assert status == 404
        assert type_ == "invalid_request_error"
        assert code == "model_not_found"

    def test_rate_limited_maps_to_429_rate_limit_exceeded(self):
        status, type_, code = get_openai_error_meta("UNIAPI_RATE_LIMITED")
        assert status == 429
        assert type_ == "rate_limit_error"
        assert code == "rate_limit_exceeded"

    def test_channel_unavailable_maps_to_503_server_error(self):
        status, type_, code = get_openai_error_meta("UNIAPI_CHANNEL_UNAVAILABLE")
        assert status == 503
        assert type_ == "api_error"
        assert code == "server_error"

    def test_unknown_code_falls_back_to_500(self):
        status, type_, code = get_openai_error_meta("UNIAPI_DOES_NOT_EXIST")
        assert status == 500
        assert type_ == "api_error"
        assert code == "server_error"

    def test_every_entry_has_valid_status(self):
        """All mapped codes produce 4xx or 5xx status codes."""
        for code in OPENAI_ERROR_MAP:
            status, _, _ = get_openai_error_meta(code)
            assert 400 <= status < 600, f"{code} has invalid status {status}"

    def test_token_expired_maps_to_401_invalid_api_key(self):
        status, type_, code = get_openai_error_meta("UNIAPI_TOKEN_EXPIRED")
        assert status == 401
        assert type_ == "authentication_error"
        assert code == "invalid_api_key"

    def test_admin_required_maps_to_403_permission_denied(self):
        status, type_, code = get_openai_error_meta("UNIAPI_ADMIN_REQUIRED")
        assert status == 403
        assert type_ == "authorization_error"
        assert code == "permission_denied"

    def test_group_access_denied_maps_to_403_permission_denied(self):
        status, type_, code = get_openai_error_meta("UNIAPI_GROUP_ACCESS_DENIED")
        assert status == 403
        assert type_ == "authorization_error"
        assert code == "permission_denied"

    def test_invalid_request_maps_to_400_invalid_request_error(self):
        status, type_, code = get_openai_error_meta("UNIAPI_INVALID_REQUEST")
        assert status == 400
        assert type_ == "invalid_request_error"
        assert code == "invalid_request_error"

    def test_resource_not_found_maps_to_404_not_found(self):
        status, type_, code = get_openai_error_meta("UNIAPI_RESOURCE_NOT_FOUND")
        assert status == 404
        assert type_ == "not_found_error"
        assert code == "resource_not_found"

    def test_service_disabled_maps_to_503_server_error(self):
        status, type_, code = get_openai_error_meta("UNIAPI_SERVICE_DISABLED")
        assert status == 503
        assert type_ == "api_error"
        assert code == "server_error"

    def test_model_not_specified_maps_to_400_model_not_found(self):
        status, type_, code = get_openai_error_meta("UNIAPI_MODEL_NOT_SPECIFIED")
        assert status == 400
        assert type_ == "invalid_request_error"
        assert code == "model_not_found"


class TestBuildOpenAIErrorResponse:
    """build_openai_error_response produces correct OpenAI format."""

    def test_returns_correct_structure(self):
        result = build_openai_error_response(
            message="Test error",
            openai_type="invalid_request_error",
            openai_code="model_not_found",
        )
        assert "error" in result
        assert result["error"]["message"] == "Test error"
        assert result["error"]["type"] == "invalid_request_error"
        assert result["error"]["param"] is None
        assert result["error"]["code"] == "model_not_found"

    def test_empty_message(self):
        result = build_openai_error_response(
            message="",
            openai_type="api_error",
            openai_code="server_error",
        )
        assert result["error"]["message"] == ""

    def test_no_extra_fields(self):
        """OpenAI format should only have the standard 4 fields."""
        result = build_openai_error_response(
            message="msg",
            openai_type="t",
            openai_code="c",
        )
        error = result["error"]
        assert set(error.keys()) == {"message", "type", "param", "code"}
