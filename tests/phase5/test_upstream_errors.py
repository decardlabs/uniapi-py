"""Phase 5, Task 2.1: Tests for upstream error mapping."""

import pytest


class TestMapUpstreamHTTPError:
    """Tests for map_upstream_http_error()."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        from app.relay.upstream_errors import map_upstream_http_error

        self.mapper = map_upstream_http_error

    def test_map_429_to_upstream_rate_limited(self):
        code, upstream = self.mapper("deepseek", 429, {"error": {"message": "Too many requests"}})
        assert code == "UPSTREAM_RATE_LIMITED"
        assert upstream["provider"] == "deepseek"
        assert upstream["status_code"] == 429

    def test_map_404_to_upstream_model_not_supported(self):
        code, upstream = self.mapper("qwen", 404, {"error": {"message": "Model not found"}})
        assert code == "UNIAPI_MODEL_NOT_SUPPORTED"
        assert upstream["provider"] == "qwen"
        assert upstream["status_code"] == 404

    def test_map_500_to_upstream_unavailable(self):
        code, upstream = self.mapper("glm", 500, {"error": {"message": "Internal server error"}})
        assert code == "UPSTREAM_UNAVAILABLE"
        assert upstream["status_code"] == 500

    def test_map_502_to_upstream_unavailable(self):
        code, upstream = self.mapper("minimax", 502, {})
        assert code == "UPSTREAM_UNAVAILABLE"

    def test_map_503_to_upstream_unavailable(self):
        code, upstream = self.mapper("kimi", 503, {})
        assert code == "UPSTREAM_UNAVAILABLE"

    def test_map_504_to_upstream_timeout(self):
        code, upstream = self.mapper("deepseek", 504, {})
        assert code == "UPSTREAM_TIMEOUT"
        assert upstream["status_code"] == 504

    def test_map_content_filter_to_provider_safety_blocked(self):
        """DeepSeek content_filter → PROVIDER_DEEPSEEK_SAFETY_BLOCKED."""
        code, upstream = self.mapper(
            "deepseek", 400,
            {"error": {"code": "content_filter", "message": "Content blocked by safety system"}},
        )
        assert code == "PROVIDER_DEEPSEEK_SAFETY_BLOCKED"
        assert upstream["code"] == "content_filter"

    def test_content_filter_only_detected_with_content_filter_code(self):
        """Regular 400 without content_filter code should NOT be safety_blocked."""
        code, _ = self.mapper("deepseek", 400, {"error": {"code": "invalid_request"}})
        assert code != "PROVIDER_DEEPSEEK_SAFETY_BLOCKED"
        assert code == "UPSTREAM_BAD_RESPONSE"

    def test_map_unknown_4xx_to_bad_response(self):
        """Unmapped 4xx falls back to UPSTREAM_BAD_RESPONSE."""
        code, upstream = self.mapper("qwen", 418, {})
        assert code == "UPSTREAM_BAD_RESPONSE"
        assert upstream["status_code"] == 418

    def test_upstream_code_extracted_from_response(self):
        """Extract upstream error code from response body."""
        code, upstream = self.mapper(
            "deepseek", 400,
            {"error": {"code": "invalid_param", "message": "Bad param"}},
        )
        assert upstream["code"] == "invalid_param"
        assert upstream["message"] == "Bad param"

    def test_upstream_message_fallback_to_str(self):
        """When response has no error.message, fall back to str of body."""
        code, upstream = self.mapper("glm", 500, "Internal Server Error")
        assert upstream["message"] == "Internal Server Error"

    def test_response_body_none_handled(self):
        """None response body should not crash."""
        code, upstream = self.mapper("deepseek", 502, None)
        assert code == "UPSTREAM_UNAVAILABLE"
        assert upstream["provider"] == "deepseek"


class TestMapUpstreamConnectionError:
    """Tests for map_upstream_connection_error()."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        from app.relay.upstream_errors import map_upstream_connection_error

        self.mapper = map_upstream_connection_error

    def test_map_timeout_to_upstream_timeout(self):
        code, upstream = self.mapper("deepseek", "timeout")
        assert code == "UPSTREAM_TIMEOUT"
        assert upstream["provider"] == "deepseek"
        assert upstream["status_code"] == 0

    def test_map_connection_refused_to_connection_failed(self):
        code, upstream = self.mapper("glm", "connection_refused")
        assert code == "UPSTREAM_CONNECTION_FAILED"

    def test_map_connection_reset_to_connection_failed(self):
        code, upstream = self.mapper("qwen", "connection_reset")
        assert code == "UPSTREAM_CONNECTION_FAILED"

    def test_map_dns_error_to_connection_failed(self):
        code, upstream = self.mapper("minimax", "dns_error")
        assert code == "UPSTREAM_CONNECTION_FAILED"

    def test_map_unknown_connection_error_to_bad_response(self):
        code, upstream = self.mapper("kimi", "something_weird")
        assert code == "UPSTREAM_BAD_RESPONSE"

    def test_map_read_timeout_to_timeout(self):
        code, _ = self.mapper("deepseek", "read_timeout")
        assert code == "UPSTREAM_TIMEOUT"

    def test_map_connect_timeout_to_timeout(self):
        code, _ = self.mapper("deepseek", "connect_timeout")
        assert code == "UPSTREAM_TIMEOUT"

    def test_connection_error_upstream_has_status_zero(self):
        _, upstream = self.mapper("deepseek", "timeout")
        assert upstream["status_code"] == 0


class TestExtractUpstreamInfo:
    """Tests for extract_upstream_info()."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        from app.relay.upstream_errors import extract_upstream_info

        self.extract = extract_upstream_info

    def test_extract_from_response_with_error_body(self):
        """Extract upstream info from a JSON error response."""
        import httpx

        resp = httpx.Response(
            status_code=429,
            json={"error": {"code": "rate_limit_exceeded", "message": "Too many requests"}},
            request=httpx.Request("POST", "https://api.deepseek.com/v1/chat/completions"),
        )
        info = self.extract("deepseek", resp)
        assert info["provider"] == "deepseek"
        assert info["status_code"] == 429
        assert info["code"] == "rate_limit_exceeded"
        assert info["message"] == "Too many requests"

    def test_extract_from_response_with_text_body(self):
        """Fallback to text body when not JSON."""
        import httpx

        resp = httpx.Response(
            status_code=502,
            text="Bad Gateway",
            request=httpx.Request("POST", "https://api.deepseek.com/v1/chat/completions"),
        )
        info = self.extract("glm", resp)
        assert info["provider"] == "glm"
        assert info["status_code"] == 502
        assert info["message"] == "Bad Gateway"

    def test_extract_request_id_from_response_headers(self):
        """Capture upstream request_id from response headers when available."""
        import httpx

        resp = httpx.Response(
            status_code=500,
            json={"error": {"message": "Internal"}},
            headers={"X-Request-Id": "upstream_req_abc"},
            request=httpx.Request("POST", "https://api.deepseek.com/v1/chat/completions"),
        )
        info = self.extract("deepseek", resp)
        assert info["request_id"] == "upstream_req_abc"
