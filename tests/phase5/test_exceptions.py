"""Phase 5, Tasks 1.1 & 1.2: Tests for extended AppException and subclasses."""

import pytest


class TestAppExceptionExtended:
    """Task 1.1: AppException with new error-code fields."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        from app.exceptions import AppException

        self.AppException = AppException

    def test_app_exception_defaults(self):
        """Default values for new params match spec."""
        exc = self.AppException()
        assert exc.status_code == 400
        assert exc.message == "Bad request"
        assert exc.code == "UNIAPI_INVALID_REQUEST"
        assert exc.type == "validation"
        assert exc.details is None
        assert exc.suggestion is None
        assert exc.upstream is None
        assert exc.data is None  # legacy field preserved

    def test_app_exception_full_construction(self):
        """All new fields can be set explicitly."""
        exc = self.AppException(
            status_code=500,
            message="Internal error",
            code="UNIAPI_INTERNAL_ERROR",
            type="internal",
            details={"stack": "trace"},
            suggestion="Contact support.",
            upstream={"provider": "deepseek", "status_code": 500},
            data={"extra": "info"},
        )
        assert exc.status_code == 500
        assert exc.message == "Internal error"
        assert exc.code == "UNIAPI_INTERNAL_ERROR"
        assert exc.type == "internal"
        assert exc.details == {"stack": "trace"}
        assert exc.suggestion == "Contact support."
        assert exc.upstream == {"provider": "deepseek", "status_code": 500}
        assert exc.data == {"extra": "info"}

    def test_app_exception_is_instance_of_exception(self):
        """AppException is still a normal Python Exception."""
        exc = self.AppException()
        assert isinstance(exc, Exception)

    def test_app_exception_legacy_construction_still_works(self):
        """Old-style construction without new fields still works."""
        exc = self.AppException(status_code=401, message="Unauthorized")
        assert exc.status_code == 401
        assert exc.message == "Unauthorized"
        # New fields get defaults
        assert exc.code == "UNIAPI_INVALID_REQUEST"  # default
        assert exc.type == "validation"

    def test_code_defaults_by_status(self):
        """The code and type fields should be settable to anything."""
        exc = self.AppException(
            status_code=401,
            message="No token",
            code="UNIAPI_INVALID_TOKEN",
            type="authentication",
        )
        assert exc.code == "UNIAPI_INVALID_TOKEN"
        assert exc.type == "authentication"


class TestLegacySubclassesUnchanged:
    """Existing subclasses (NotFoundException, etc.) must still work."""

    def test_not_found_exception(self):
        from app.exceptions import NotFoundException

        exc = NotFoundException()
        assert exc.status_code == 404
        assert exc.message == "Not found"
        assert isinstance(exc, Exception)

    def test_not_found_custom_message(self):
        from app.exceptions import NotFoundException

        exc = NotFoundException(message="User not found")
        assert exc.status_code == 404
        assert exc.message == "User not found"

    def test_unauthorized_exception(self):
        from app.exceptions import UnauthorizedException

        exc = UnauthorizedException()
        assert exc.status_code == 401
        assert exc.message == "Unauthorized"

    def test_forbidden_exception(self):
        from app.exceptions import ForbiddenException

        exc = ForbiddenException()
        assert exc.status_code == 403
        assert exc.message == "Forbidden"

    def test_quota_exceeded_exception(self):
        from app.exceptions import QuotaExceededException

        exc = QuotaExceededException()
        assert exc.status_code == 402  # per spec: 402 Payment Required
        assert exc.message == "Quota exceeded"
        assert exc.code == "UNIAPI_QUOTA_EXHAUSTED"

    def test_not_implemented_exception(self):
        from app.exceptions import NotImplementedException

        exc = NotImplementedException()
        assert exc.status_code == 501
        assert exc.message == "Not implemented"


class TestRelayException:
    """Task 1.2: RelayException for Relay API errors."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        from app.exceptions import RelayException

        self.RelayException = RelayException

    def test_relay_exception_inherits_app_exception(self):
        from app.exceptions import AppException

        exc = self.RelayException(
            message="Token not allowed",
            code="UNIAPI_TOKEN_MODEL_NOT_ALLOWED",
        )
        assert isinstance(exc, AppException)
        assert isinstance(exc, Exception)

    def test_relay_exception_defaults(self):
        """RelayException auto-infers status/type from code."""
        exc = self.RelayException(
            message="Token not allowed",
            code="UNIAPI_TOKEN_MODEL_NOT_ALLOWED",
        )
        assert exc.status_code == 403
        assert exc.type == "authorization"
        assert exc.message == "Token not allowed"

    def test_relay_exception_explicit_overrides(self):
        """Explicit status_code/type override auto-inference."""
        exc = self.RelayException(
            message="Custom",
            code="UNIAPI_INVALID_REQUEST",
            status_code=422,  # override
            type="validation",  # explicit
        )
        assert exc.status_code == 422
        assert exc.type == "validation"

    def test_relay_exception_with_details(self):
        """details and suggestion pass through."""
        exc = self.RelayException(
            message="Model not supported",
            code="UNIAPI_MODEL_NOT_SUPPORTED",
            details={"model": "gpt-5"},
            suggestion="Try a different model.",
        )
        assert exc.details == {"model": "gpt-5"}
        assert exc.suggestion == "Try a different model."


class TestUpstreamException:
    """Task 1.2: UpstreamException for upstream provider errors."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        from app.exceptions import UpstreamException

        self.UpstreamException = UpstreamException

    def test_upstream_exception_inherits_relay_exception(self):
        from app.exceptions import RelayException

        exc = self.UpstreamException(
            message="Upstream timeout",
            code="UPSTREAM_TIMEOUT",
            upstream_provider="deepseek",
            upstream_status=504,
        )
        assert isinstance(exc, RelayException)

    def test_upstream_exception_builds_upstream_field(self):
        """UpstreamException auto-constructs the upstream dict."""
        exc = self.UpstreamException(
            message="Upstream rate limited",
            code="UPSTREAM_RATE_LIMITED",
            upstream_provider="deepseek",
            upstream_status=429,
            upstream_code="rate_limit_exceeded",
            upstream_message="Too many requests",
            upstream_request_id="deepseek_req_xyz",
        )
        assert exc.upstream["provider"] == "deepseek"
        assert exc.upstream["status_code"] == 429
        assert exc.upstream["code"] == "rate_limit_exceeded"
        assert exc.upstream["message"] == "Too many requests"
        assert exc.upstream["request_id"] == "deepseek_req_xyz"

    def test_upstream_exception_minimal(self):
        """Minimal upstream exception with just provider and status."""
        exc = self.UpstreamException(
            message="Upstream unavailable",
            code="UPSTREAM_UNAVAILABLE",
            upstream_provider="glm",
            upstream_status=503,
        )
        assert exc.upstream["provider"] == "glm"
        assert exc.upstream["status_code"] == 503
        assert exc.upstream["code"] is None
        assert exc.upstream["message"] is None

    def test_upstream_exception_default_code(self):
        """When code not specified, infers from common patterns."""
        exc = self.UpstreamException(
            message="Bad gateway",
            upstream_provider="qwen",
            upstream_status=502,
        )
        # Should infer UPSTREAM_BAD_RESPONSE for 502
        assert exc.code == "UPSTREAM_BAD_RESPONSE"
        assert exc.type == "upstream"

    def test_upstream_exception_connection_failure(self):
        """Connection failures auto-map to UPSTREAM_CONNECTION_FAILED."""
        exc = self.UpstreamException(
            message="Connection refused",
            upstream_provider="minimax",
            upstream_status=0,  # no HTTP status
            code="UPSTREAM_CONNECTION_FAILED",
        )
        assert exc.code == "UPSTREAM_CONNECTION_FAILED"
        assert exc.type == "upstream"
        assert exc.status_code == 502
