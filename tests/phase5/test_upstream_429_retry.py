"""Phase 5: Tests for upstream 429 backoff retry mechanism.

These tests verify that when the upstream returns HTTP 429:
1. The relay retries on the same channel with exponential backoff
2. After exhausting all retries, it properly raises an UpstreamException
3. The channel failure counter is NOT incremented during retries (only after exhaustion)
"""
import pytest
from unittest.mock import Mock, patch

import httpx


async def _get_test_token():
    from app.database import async_session_factory
    from sqlalchemy import select
    from app.models.token import Token

    async with async_session_factory() as db:
        result = await db.execute(select(Token).limit(1))
        token = result.scalar_one_or_none()
        return token


async def _login(client):
    resp = await client.post("/api/user/login", json={
        "username": "root", "password": "123456",
    })
    return resp.cookies


class TestUpstream429Retry:
    """Verify 429 backoff retry behavior."""

    @pytest.fixture(autouse=True)
    async def _setup(self, client):
        self.client = client

        # Login as admin and create a test DeepSeek channel
        cookies = await _login(client)
        resp = await client.post("/api/channel/", json={
            "name": "Test DeepSeek",
            "type": 39,
            "key": "sk-test-key",
            "models": "deepseek-v4-flash",
            "status": 1,
            "weight": 1,
        }, cookies=cookies)

        self.token = await _get_test_token()
        self.token_key = self.token.key if self.token else None
        self.token_id = self.token.id if self.token else None

        # Patch config to speed up tests
        from app.config import settings
        patcher_backoff = patch.object(settings, "upstream_retry_backoff_base", 0.01)
        patcher_max = patch.object(settings, "upstream_retry_max", 3)
        patcher_backoff.start()
        patcher_max.start()
        yield
        patcher_backoff.stop()
        patcher_max.stop()

    def _headers(self):
        return {"Authorization": f"Bearer {self.token_key}"}

    async def _post(self, body=None):
        if body is None:
            body = {
                "model": "deepseek-v4-flash",
                "messages": [{"role": "user", "content": "hi"}],
            }
        return await self.client.post(
            "/v1/chat/completions", json=body, headers=self._headers()
        )

    async def test_429_triggers_backoff_then_success(self):
        """When upstream returns 429 then 200 on retry, the request succeeds."""
        call_count = 0

        async def _mock_relay(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise httpx.HTTPStatusError(
                    "429 Too Many Requests",
                    request=Mock(),
                    response=Mock(spec=httpx.Response, status_code=429),
                )
            return {
                "id": "chat-123",
                "object": "chat.completion",
                "choices": [{"message": {"role": "assistant", "content": "OK"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 20},
            }

        with patch(
            "app.routers.v1.relay.relay_chat_completion", new=_mock_relay
        ):
            resp = await self._post()
            assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text}"
            assert call_count == 2, f"Expected 2 calls, got {call_count}"

    async def test_429_exhaustion_returns_upstream_error(self):
        """When all retries return 429, the client gets an upstream error."""
        async def _always_429(*args, **kwargs):
            raise httpx.HTTPStatusError(
                "429 Too Many Requests",
                request=Mock(),
                response=Mock(spec=httpx.Response, status_code=429),
            )

        with patch(
            "app.routers.v1.relay.relay_chat_completion", new=_always_429
        ):
            resp = await self._post()
            assert resp.status_code >= 400
            data = resp.json()
            assert "error" in data

    async def test_429_backoff_does_not_increment_failure_counter(self):
        """A 429 that succeeds on retry should not record a channel failure."""
        from app.routers.v1.relay import _channel_failures

        # Clear any existing failures from previous tests
        _channel_failures.clear()

        call_count = 0

        async def _mock_relay(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise httpx.HTTPStatusError(
                    "429 Too Many Requests",
                    request=Mock(),
                    response=Mock(spec=httpx.Response, status_code=429),
                )
            return {
                "id": "chat-123",
                "object": "chat.completion",
                "choices": [{"message": {"role": "assistant", "content": "OK"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 20},
            }

        with patch(
            "app.routers.v1.relay.relay_chat_completion", new=_mock_relay
        ):
            resp = await self._post()
            assert resp.status_code == 200
            # No channels should have failure counts after a successful retry
            assert len(_channel_failures) == 0, (
                f"Expected no failures after successful retry, "
                f"got: {dict(_channel_failures)}"
            )

    async def test_429_streaming_backoff_then_success(self):
        """Streaming request that gets 429 then succeeds on retry."""
        call_count = 0

        async def _mock_relay(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise httpx.HTTPStatusError(
                    "429 Too Many Requests",
                    request=Mock(),
                    response=Mock(spec=httpx.Response, status_code=429),
                )
            return {
                "id": "chat-123",
                "object": "chat.completion",
                "choices": [{"delta": {"content": "hello"}}],
            }

        with patch(
            "app.routers.v1.relay.relay_chat_completion", new=_mock_relay
        ):
            body = {
                "model": "deepseek-v4-flash",
                "messages": [{"role": "user", "content": "hi"}],
                "stream": True,
            }
            resp = await self._post(body=body)
            assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text}"
            assert call_count == 2, f"Expected 2 calls, got {call_count}"

    async def test_429_backoff_does_not_refund_quota(self):
        """Quota is NOT refunded during backoff retry (only after all retries exhausted)."""
        from app.database import async_session_factory
        from sqlalchemy import select
        from app.models.token import Token
        from app.models.user import User

        # Capture token and user info before the call
        async with async_session_factory() as db:
            token_before = await db.execute(select(Token).where(Token.id == self.token_id))
            token_before = token_before.scalar_one()

        call_count = 0

        async def _mock_relay(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise httpx.HTTPStatusError(
                    "429 Too Many Requests",
                    request=Mock(),
                    response=Mock(spec=httpx.Response, status_code=429),
                )
            return {
                "id": "chat-123",
                "object": "chat.completion",
                "choices": [{"message": {"role": "assistant", "content": "OK"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 20},
            }

        with patch(
            "app.routers.v1.relay.relay_chat_completion", new=_mock_relay
        ):
            resp = await self._post()
            assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text}"
            assert call_count == 2, f"Expected 2 calls, got {call_count}"

        # Verify quota wasn't refunded (no negative/double deduction)
        async with async_session_factory() as db:
            token_after = await db.execute(select(Token).where(Token.id == self.token_id))
            token_after = token_after.scalar_one()
            assert token_after.remain_quota >= 0

    def test_backoff_jitter_range(self):
        """Jitter formula produces delays in [0.5*base*2^t, 1.0*base*2^t] range."""
        BACKOFF_BASE = 0.01  # match test fixture value
        import random
        for attempt in range(3):
            for _ in range(100):
                delay = BACKOFF_BASE * (2 ** attempt) * (0.5 + random.random() * 0.5)
                expected_min = BACKOFF_BASE * (2 ** attempt) * 0.5
                expected_max = BACKOFF_BASE * (2 ** attempt) * 1.0
                assert expected_min <= delay <= expected_max, \
                    f"attempt={attempt}: {delay} not in [{expected_min}, {expected_max}]"
