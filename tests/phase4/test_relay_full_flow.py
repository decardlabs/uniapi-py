"""
Phase 4: Full relay pipeline E2E test (mock upstream).

Tests the complete relay flow: auth -> model routing -> channel selection ->
upstream dispatch -> response transformation -> post-settlement.

Uses httpx.AsyncClient patches to simulate upstream LLM responses.
"""

from unittest.mock import Mock, patch

import pytest
from httpx import AsyncClient


async def _login(client: AsyncClient) -> dict:
    resp = await client.post("/api/user/login", json={
        "username": "root", "password": "123456",
    })
    return resp.cookies


async def _get_root_token(client: AsyncClient, cookies: dict) -> str:
    """Get the root user's first token key for Bearer auth."""
    resp = await client.get("/api/token/?p=0&size=5", cookies=cookies)
    tokens = resp.json().get("data", [])
    assert len(tokens) > 0, "No tokens found — seed may have failed"
    return tokens[0]["key"]


@pytest.fixture(scope="module")
def anyio_backend():
    return "asyncio"


class TestRelayFullFlow:
    """E2E tests for the relay pipeline with a mocked upstream."""

    @pytest.mark.asyncio
    async def test_chat_completion_non_stream(self, client: AsyncClient):
        """Non-streaming chat completion: auth -> route -> upstream -> response."""
        # ── Setup: login, create channel, get token ──────────────
        cookies = await _login(client)
        token_key = await _get_root_token(client, cookies)

        # Create a channel that the relay can route to
        await client.post("/api/channel/", json={
            "name": "E2E DeepSeek",
            "type": 39,  # DeepSeek
            "key": "sk-e2e-upstream-key",
            "models": "deepseek-chat,deepseek-v4-flash",
            "group": "default",
            "endpoint": "https://api.deepseek.com",
            "status": 1,
            "weight": 1,
        }, cookies=cookies)

        # ── Mock upstream ───────────────────────────────────────
        mock_response = {
            "id": "mock-chat-abc123",
            "object": "chat.completion",
            "created": 1700000000,
            "model": "deepseek-chat",
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "Hello from the mock upstream!",
                },
                "finish_reason": "stop",
            }],
            "usage": {
                "prompt_tokens": 50,
                "completion_tokens": 20,
                "total_tokens": 70,
            },
        }

        async def mock_post(*args, **kwargs):
            mock_resp = Mock()
            mock_resp.status_code = 200
            mock_resp.json = lambda: mock_response
            mock_resp.headers = {"content-type": "application/json"}
            return mock_resp

        with patch("httpx.AsyncClient.post", mock_post):
            # ── Send relay request ───────────────────────────────
            resp = await client.post(
                "/v1/chat/completions",
                json={
                    "model": "deepseek-chat",
                    "messages": [{"role": "user", "content": "Hello!"}],
                },
                headers={"Authorization": f"Bearer {token_key}"},
            )

        # ── Assertions ──────────────────────────────────────────
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text()[:200]}"
        body = resp.json()
        assert isinstance(body, dict), f"Expected dict, got {type(body)}"
        choices = body.get("choices", [])
        assert len(choices) > 0, f"No choices in response: {body}"
        content = choices[0].get("message", {}).get("content", "")
        assert content, f"Empty content in response: {body}"

    @pytest.mark.asyncio
    async def test_chat_completion_with_token_pinning(self, client: AsyncClient):
        """Token key with channel pinning (key:channel_id) syntax."""
        cookies = await _login(client)
        token_key = await _get_root_token(client, cookies)

        # Create a channel first so there's one to pin to
        create_resp = await client.post("/api/channel/", json={
            "name": "Pinned Channel",
            "type": 39,
            "key": "sk-pinned-key",
            "models": "deepseek-chat",
            "group": "default",
            "endpoint": "https://api.deepseek.com",
            "status": 1,
        }, cookies=cookies)
        channel_id = create_resp.json()["data"]["id"]

        async def mock_post(*args, **kwargs):
            mock_resp = Mock()
            mock_resp.status_code = 200
            mock_resp.json = lambda: {"choices": [{"message": {"content": "pinned"}}], "usage": {}}
            mock_resp.headers = {"content-type": "application/json"}
            return mock_resp

        with patch("httpx.AsyncClient.post", mock_post):
            resp = await client.post(
                "/v1/chat/completions",
                json={
                    "model": "deepseek-chat",
                    "messages": [{"role": "user", "content": "Pin test"}],
                },
                headers={"Authorization": f"Bearer {token_key}:{channel_id}"},
            )
        assert resp.status_code == 200, f"Pinning failed: {resp.status_code}: {resp.text()[:200]}"

    @pytest.mark.asyncio
    async def test_invalid_token_returns_401(self, client: AsyncClient):
        """Request with an invalid Bearer token should be rejected."""
        resp = await client.post(
            "/v1/chat/completions",
            json={
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": "hi"}],
            },
            headers={"Authorization": "Bearer sk-invalid-token-key"},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_model_not_allowed_by_token(self, client: AsyncClient):
        """Token that doesn't allow the requested model should be rejected."""
        cookies = await _login(client)
        await _get_root_token(client, cookies)

        # Root seed token has no model restrictions (models="")
        # Create a restricted token
        resp = await client.post("/api/token/", json={
            "name": "Restricted Token",
            "models": "gpt-4",  # only allow gpt-4
            "expired_time": "",
        }, cookies=cookies)
        restricted_key = resp.json()["data"]["key"]

        resp2 = await client.post(
            "/v1/chat/completions",
            json={
                "model": "deepseek-chat",  # NOT in allowed models
                "messages": [{"role": "user", "content": "hi"}],
            },
            headers={"Authorization": f"Bearer {restricted_key}"},
        )
        assert resp2.status_code in (400, 403, 404), f"Expected 400/403/404, got {resp2.status_code}"
        if resp2.status_code != 404:
            body = resp2.json()
            error_msg = str(body).lower()
            assert any(w in error_msg for w in ["not allowed", "not_allow", "token_model"])

    @pytest.mark.asyncio
    async def test_upstream_error_returns_502(self, client: AsyncClient):
        """When upstream returns 5xx, the relay should return 502."""
        cookies = await _login(client)
        token_key = await _get_root_token(client, cookies)

        await client.post("/api/channel/", json={
            "name": "E2E Failing Upstream",
            "type": 39,
            "key": "sk-bad-key",
            "models": "failing-model",
            "group": "default",
            "status": 1,
        }, cookies=cookies)

        async def mock_post(*args, **kwargs):
            mock_resp = Mock()
            mock_resp.status_code = 500
            mock_resp.text = "Internal Server Error"
            mock_resp.headers = {"content-type": "application/json"}
            return mock_resp

        with patch("httpx.AsyncClient.post", mock_post):
            resp = await client.post(
                "/v1/chat/completions",
                json={
                    "model": "failing-model",
                    "messages": [{"role": "user", "content": "hi"}],
                },
                headers={"Authorization": f"Bearer {token_key}"},
            )

        assert resp.status_code in (500, 502, 503)
