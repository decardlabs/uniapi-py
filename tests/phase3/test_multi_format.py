"""Phase 3: Multi-format support - NATIVE_FORMATS routing (TDD).

DeepSeek natively supports claude_messages format, so requests to
/v1/messages should be proxied directly without format conversion.
"""
import pytest
from httpx import AsyncClient


async def _login(client: AsyncClient) -> dict:
    resp = await client.post("/api/user/login", json={
        "username": "root", "password": "123456",
    })
    return resp.cookies


@pytest.mark.asyncio
async def test_deepseek_native_formats_include_claude(client: AsyncClient):
    """DeepSeekAdaptor should declare claude_messages in NATIVE_FORMATS."""
    from app.relay.adaptors.deepseek.adaptor import DeepSeekAdaptor
    adp = DeepSeekAdaptor()
    assert "claude_messages" in adp.NATIVE_FORMATS
    assert "chat_completions" in adp.NATIVE_FORMATS


@pytest.mark.asyncio
async def test_deepseek_get_url_for_claude_messages(client: AsyncClient):
    """DeepSeek adaptor should return /v1/messages path for ClaudeMessages mode."""
    from app.relay.adaptors.deepseek.adaptor import DeepSeekAdaptor
    from app.relay.meta import RelayMeta
    meta = RelayMeta(base_url="https://api.deepseek.com/v1")
    url = DeepSeekAdaptor().get_request_url(meta, 12)  # 12=CLAUDE_MESSAGES
    assert "api.deepseek.com/anthropic/v1/messages" in url


@pytest.mark.asyncio
async def test_deepseek_get_url_for_chat(client: AsyncClient):
    """DeepSeek adaptor should return /v1/chat/completions for ChatCompletions mode."""
    from app.relay.adaptors.deepseek.adaptor import DeepSeekAdaptor
    from app.relay.meta import RelayMeta
    meta = RelayMeta(base_url="https://api.deepseek.com/v1")
    url = DeepSeekAdaptor().get_request_url(meta, 1)  # 1=CHAT_COMPLETIONS
    assert "/chat/completions" in url


@pytest.mark.asyncio
async def test_v1_messages_endpoint_registered(client: AsyncClient):
    """POST /v1/messages should be registered (not 404)."""
    cookies = await _login(client)
    # Create a token to use
    token_resp = await client.post(
        "/api/token/",
        json={"name": "msg-test", "unlimited_quota": True},
        cookies=cookies,
    )
    token_key = token_resp.json()["data"]["key"]

    resp = await client.post(
        "/v1/messages",
        json={
            "model": "deepseek-v4-pro",
            "messages": [{"role": "user", "content": "Hello"}],
        },
        headers={"Authorization": f"Bearer {token_key}"},
    )
    # Should not be 404 (route exists). May be 400+ if DeepSeek unreachable,
    # but the endpoint itself should be defined.
    assert resp.status_code != 404


@pytest.mark.asyncio
async def test_v1_responses_endpoint_registered(client: AsyncClient):
    """POST /v1/responses should be registered (not 404)."""
    cookies = await _login(client)
    token_resp = await client.post(
        "/api/token/",
        json={"name": "resp-test", "unlimited_quota": True},
        cookies=cookies,
    )
    token_key = token_resp.json()["data"]["key"]

    resp = await client.post(
        "/v1/responses",
        json={
            "model": "deepseek-v4-pro",
            "input": "Hello",
        },
        headers={"Authorization": f"Bearer {token_key}"},
    )
    assert resp.status_code != 404


@pytest.mark.asyncio
async def test_base_adaptor_native_formats(client: AsyncClient):
    """BaseAdaptor should default to only chat_completions."""
    from app.relay.adaptor import BaseAdaptor

    class TestAdaptor(BaseAdaptor):
        provider_name = "test"
        def get_request_url(self, meta, mode=1): return "http://test"
        def setup_request_headers(self, api_key=""): return {}
        async def convert_request(self, body, meta): return body
        def get_supported_models(self): return {}

    adp = TestAdaptor()
    assert "chat_completions" in adp.NATIVE_FORMATS
    assert "claude_messages" not in adp.NATIVE_FORMATS
