"""Phase: GLM adaptor tests (TDD).

GLM natively supports claude_messages via the Anthropic-compatible endpoint.
"""

import time
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_glm_native_formats(client: AsyncClient):
    """GLMAdaptor should keep claude_messages on conversion path."""
    from app.relay.adaptors.glm.adaptor import GLMAdaptor
    adp = GLMAdaptor()
    assert "chat_completions" in adp.NATIVE_FORMATS
    assert "claude_messages" not in adp.NATIVE_FORMATS


@pytest.mark.asyncio
async def test_glm_get_url_for_chat(client: AsyncClient):
    """Chat mode should use the paas v4 endpoint."""
    from app.relay.adaptors.glm.adaptor import GLMAdaptor
    from app.relay.meta import RelayMeta
    meta = RelayMeta(base_url="https://open.bigmodel.cn/api/paas/v4")
    url = GLMAdaptor().get_request_url(meta, 1)  # CHAT_COMPLETIONS
    assert "/api/paas/v4/chat/completions" in url


@pytest.mark.asyncio
async def test_glm_get_url_for_claude(client: AsyncClient):
    """Claude mode should use the Anthropic-compatible endpoint."""
    from app.relay.adaptors.glm.adaptor import GLMAdaptor
    from app.relay.meta import RelayMeta
    meta = RelayMeta(base_url="https://open.bigmodel.cn/api/paas/v4")
    url = GLMAdaptor().get_request_url(meta, 12)  # CLAUDE_MESSAGES
    assert url == "https://open.bigmodel.cn/api/anthropic/v1/messages"


@pytest.mark.asyncio
async def test_glm_supports_native_format(client: AsyncClient):
    """supports_native_format should be correct for GLM."""
    from app.relay.adaptors.glm.adaptor import GLMAdaptor
    adp = GLMAdaptor()
    assert adp.supports_native_format(1) is True   # ChatCompletions
    assert adp.supports_native_format(12) is False  # ClaudeMessages
    assert adp.supports_native_format(5) is False  # ImagesGenerations


@pytest.mark.asyncio
async def test_glm_supported_models(client: AsyncClient):
    """GLM adaptor should list supported models with pricing."""
    from app.relay.adaptors.glm.adaptor import GLMAdaptor
    models = GLMAdaptor().get_supported_models()
    assert "glm-5.2" in models
    assert "glm-4.7" in models
    assert models["glm-5.1"].input_ratio > 0
    assert models["glm-5.1"].output_ratio > 0


@pytest.mark.asyncio
async def test_glm_registered_in_registry(client: AsyncClient):
    """GLM adaptor should be registered in the global registry."""
    from app.relay.registry import registry
    adp = registry.get(41)  # GLM channel type
    assert adp is not None
    assert adp.provider_name == "glm"


@pytest.mark.asyncio
async def test_glm_jwt_token_generation(client: AsyncClient):
    """GLM API key (id.secret) should generate a valid JWT."""
    from app.relay.adaptors.glm.auth import generate_glm_token
    token = generate_glm_token("test-id.test-secret")
    assert token is not None
    assert len(token) > 20
    assert isinstance(token, str)
    # Token should be cached on second call
    token2 = generate_glm_token("test-id.test-secret")
    assert token == token2


@pytest.mark.asyncio
async def test_glm_invalid_key_format(client: AsyncClient):
    """Invalid API key format should raise an error."""
    from app.relay.adaptors.glm.auth import generate_glm_token
    with pytest.raises(ValueError, match="expect.*id\\.secret"):
        generate_glm_token("invalid-key-format")


@pytest.mark.asyncio
async def test_glm_setup_headers(client: AsyncClient):
    """GLM adaptor should set proper auth headers."""
    from app.relay.adaptors.glm.adaptor import GLMAdaptor
    headers = GLMAdaptor().setup_request_headers("test-id.test-secret")
    assert "Authorization" in headers
    assert headers["Authorization"].startswith("eyJ")  # JWT starts with base64
    assert headers["Content-Type"] == "application/json"


@pytest.mark.asyncio
async def test_glm_relay_uses_adaptor_headers(client: AsyncClient, monkeypatch):
    """Relay should pass adaptor-generated GLM headers to upstream requests."""

    # Login and create a relay token
    login_resp = await client.post("/api/user/login", json={"username": "root", "password": "123456"})
    cookies = login_resp.cookies

    token_resp = await client.post(
        "/api/token/",
        json={"name": "glm-relay-test", "unlimited_quota": True},
        cookies=cookies,
    )
    token_key = token_resp.json()["data"]["key"]

    # Create a GLM channel with id.secret API key format
    await client.post(
        "/api/channel/",
        json={
            "name": "Test GLM",
            "type": 41,
            "key": "test-id.test-secret",
            "base_url": "https://open.bigmodel.cn/api/paas/v4",
            "models": "glm-5.2",
            "group": "default",
        },
        cookies=cookies,
    )

    captured: dict[str, dict[str, str]] = {}

    async def _fake_relay_chat_completion(**kwargs):
        captured["headers"] = kwargs.get("request_headers") or {}
        return {
            "id": "chatcmpl-test",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": "glm-5.2",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }

    import app.routers.v1.relay as relay_module

    monkeypatch.setattr(relay_module, "relay_chat_completion", _fake_relay_chat_completion)

    resp = await client.post(
        "/v1/chat/completions",
        json={
            "model": "glm-5.2",
            "messages": [{"role": "user", "content": "hello"}],
            "stream": False,
        },
        headers={"Authorization": f"Bearer {token_key}"},
    )

    assert resp.status_code == 200
    assert captured["headers"]["Authorization"].startswith("eyJ")
    assert captured["headers"]["Content-Type"] == "application/json"


@pytest.mark.asyncio
async def test_glm_messages_use_chat_conversion_path(client: AsyncClient, monkeypatch):
    """/v1/messages for GLM should convert to chat payload and chat endpoint."""
    login_resp = await client.post("/api/user/login", json={"username": "root", "password": "123456"})
    cookies = login_resp.cookies

    token_resp = await client.post(
        "/api/token/",
        json={"name": "glm-msg-convert", "unlimited_quota": True},
        cookies=cookies,
    )
    token_key = token_resp.json()["data"]["key"]

    await client.post(
        "/api/channel/",
        json={
            "name": "Test GLM Msg Convert",
            "type": 41,
            "key": "test-id.test-secret",
            "base_url": "https://open.bigmodel.cn/api/paas/v4",
            "models": "glm-5.2",
            "group": "default",
        },
        cookies=cookies,
    )

    captured = {}

    async def _fake_relay_chat_completion(**kwargs):
        captured["upstream_url"] = kwargs.get("upstream_url")
        captured["body"] = kwargs.get("body") or {}
        return {
            "id": "chatcmpl-test-msg",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": "glm-5.2",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }

    import app.routers.v1.relay as relay_module

    monkeypatch.setattr(relay_module, "relay_chat_completion", _fake_relay_chat_completion)

    resp = await client.post(
        "/v1/messages",
        json={
            "model": "glm-5.2",
            "max_tokens": 64,
            "messages": [{"role": "user", "content": [{"type": "text", "text": "hello"}]}],
        },
        headers={"Authorization": f"Bearer {token_key}"},
    )

    assert resp.status_code == 200
    assert captured["upstream_url"].endswith("/chat/completions")
    assert captured["body"]["messages"][0]["content"] == "hello"
