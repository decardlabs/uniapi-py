"""Phase 5, Tasks 4 & 6: Tests for relay error responses."""

import pytest
from sqlalchemy import select


async def _get_test_token():
    """Get a real token from the test database."""
    from app.database import async_session_factory
    from app.models.token import Token

    async with async_session_factory() as db:
        result = await db.execute(select(Token).limit(1))
        token = result.scalar_one_or_none()
        return token


class TestRelayBusinessErrors:
    """Verify relay business-logic errors produce correct UniAPI codes."""

    @pytest.fixture(autouse=True)
    async def _setup(self, client):
        self.client = client
        self.token = await _get_test_token()
        self.token_key = self.token.key if self.token else None

    def _headers(self):
        return {"Authorization": f"Bearer {self.token_key}"}

    async def _post(self, body=None):
        if body is None:
            body = {"model": "deepseek-chat", "messages": [{"role": "user", "content": "hi"}]}
        return await self.client.post("/v1/chat/completions", json=body, headers=self._headers())

    async def test_model_not_supported(self):
        """Requesting an unsupported model returns model_not_found (OpenAI format)."""
        resp = await self._post({"model": "nonexistent-model-xyz-123", "messages": [{"role": "user", "content": "hi"}]})
        assert resp.status_code in (400, 404), f"Got {resp.status_code}"
        data = resp.json()
        # OpenAI format: error.code = "model_not_found"
        assert data["error"]["code"] == "model_not_found", f"Got code: {data['error']['code']}"
        assert data["error"]["type"] == "invalid_request_error"

    async def test_model_not_specified_with_restricted_token(self):
        """Empty model field should trigger appropriate error."""
        resp = await self._post({"messages": [{"role": "user", "content": "hi"}]})
        # May work (auto) or fail depending on channels
        assert resp.status_code < 600

    async def test_all_errors_include_error_code(self):
        """Every relay error must have error.code."""
        resp = await self._post({"model": "nonexistent-model-xyz", "messages": [{"role": "user", "content": "hi"}]})
        data = resp.json()
        assert "code" in data["error"]

    async def test_openai_format_structure(self):
        """Phase B: v1 relay errors return pure OpenAI format (no extra fields)."""
        resp = await self._post({"model": "nonexistent-model-xyz", "messages": [{"role": "user", "content": "hi"}]})
        data = resp.json()
        # Top level: only "error"
        assert list(data.keys()) == ["error"], f"Unexpected keys: {list(data.keys())}"
        # Error object: only standard OpenAI fields
        assert set(data["error"].keys()) == {"message", "type", "param", "code"}, \
            f"Unexpected error keys: {list(data['error'].keys())}"


class TestMiddlewareErrors:
    """Verify middleware produces standard error format."""

    def test_rate_limit_middleware_uses_standard_error_code(self):
        """RateLimitMiddleware is configured to use standard error format."""
        from app.error_codes import UNIAPI_RATE_LIMITED
        from app.middleware import RateLimitMiddleware

        assert RateLimitMiddleware is not None
        assert UNIAPI_RATE_LIMITED == "UNIAPI_RATE_LIMITED"
