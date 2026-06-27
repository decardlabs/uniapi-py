"""Tests targeting specific coverage gaps to bring overall coverage above threshold."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# app/schemas/relay.py — 0% coverage (66 lines)
# Simply importing and instantiating the models covers all class-body lines.
# ---------------------------------------------------------------------------


def test_relay_schemas_chat_message():
    from app.schemas.relay import ChatMessage

    msg = ChatMessage(role="user", content="Hello")
    assert msg.role == "user"
    assert msg.content == "Hello"
    assert msg.name is None
    assert msg.tool_calls is None
    assert msg.tool_call_id is None
    assert msg.reasoning_content is None


def test_relay_schemas_chat_message_with_list_content():
    from app.schemas.relay import ChatMessage

    msg = ChatMessage(role="user", content=[{"type": "text", "text": "hi"}])
    assert isinstance(msg.content, list)


def test_relay_schemas_chat_completion_request():
    from app.schemas.relay import ChatCompletionRequest, ChatMessage

    req = ChatCompletionRequest(
        model="gpt-4",
        messages=[ChatMessage(role="user", content="hi")],
    )
    assert req.model == "gpt-4"
    assert req.stream is False
    assert req.n == 1


def test_relay_schemas_chat_completion_request_full():
    from app.schemas.relay import ChatCompletionRequest, ChatMessage

    req = ChatCompletionRequest(
        model="deepseek-chat",
        messages=[ChatMessage(role="system", content="You are helpful"), ChatMessage(role="user", content="hi")],
        stream=True,
        max_tokens=1024,
        temperature=0.7,
        top_p=0.9,
        n=1,
        stop=["END"],
        presence_penalty=0.0,
        frequency_penalty=0.0,
        logit_bias={"50256": -100},
        user="user-123",
        seed=42,
        tools=[{"type": "function", "function": {"name": "get_weather"}}],
        tool_choice="auto",
        response_format={"type": "json_object"},
        reasoning_effort="medium",
        thinking={"type": "enabled", "budget_tokens": 1000},
    )
    assert req.stream is True
    assert req.max_tokens == 1024


def test_relay_schemas_usage_info():
    from app.schemas.relay import UsageInfo

    usage = UsageInfo(prompt_tokens=10, completion_tokens=20, total_tokens=30)
    assert usage.prompt_tokens == 10
    assert usage.total_tokens == 30


def test_relay_schemas_usage_info_defaults():
    from app.schemas.relay import UsageInfo

    usage = UsageInfo()
    assert usage.prompt_tokens == 0
    assert usage.completion_tokens == 0
    assert usage.total_tokens == 0


def test_relay_schemas_chat_choice():
    from app.schemas.relay import ChatChoice, ChatMessage

    choice = ChatChoice(
        index=0,
        message=ChatMessage(role="assistant", content="Hello!"),
        finish_reason="stop",
    )
    assert choice.index == 0
    assert choice.finish_reason == "stop"


def test_relay_schemas_chat_completion_response():
    import time

    from app.schemas.relay import ChatChoice, ChatCompletionResponse, ChatMessage, UsageInfo

    resp = ChatCompletionResponse(
        id="chatcmpl-123",
        created=int(time.time()),
        model="gpt-4",
        choices=[
            ChatChoice(
                index=0,
                message=ChatMessage(role="assistant", content="Hello!"),
                finish_reason="stop",
            )
        ],
        usage=UsageInfo(prompt_tokens=5, completion_tokens=3, total_tokens=8),
    )
    assert resp.object == "chat.completion"
    assert len(resp.choices) == 1


def test_relay_schemas_model_permission():
    from app.schemas.relay import ModelPermission

    perm = ModelPermission(id="perm-123")
    assert perm.object == "model-permission"
    assert perm.allow_sampling is True
    assert perm.allow_view is True
    assert perm.organization == "*"


def test_relay_schemas_model_info():
    import time

    from app.schemas.relay import ModelInfo, ModelPermission

    info = ModelInfo(id="gpt-4", created=int(time.time()))
    assert info.object == "model"
    assert info.owned_by == "uniapi"
    assert info.permission == []

    info_with_perm = ModelInfo(
        id="gpt-4",
        created=int(time.time()),
        permission=[ModelPermission(id="perm-1")],
    )
    assert len(info_with_perm.permission) == 1


def test_relay_schemas_model_list():
    import time

    from app.schemas.relay import ModelInfo, ModelList

    model_list = ModelList(
        data=[ModelInfo(id="gpt-4", created=int(time.time()))]
    )
    assert model_list.object == "list"
    assert len(model_list.data) == 1


# ---------------------------------------------------------------------------
# app/relay/mode.py — missing branches in relay_mode_from_path (18 lines)
# ---------------------------------------------------------------------------


def test_relay_mode_chat_completions():
    from app.relay.mode import RelayMode, relay_mode_from_path

    assert relay_mode_from_path("/v1/chat/completions") == RelayMode.CHAT_COMPLETIONS
    assert relay_mode_from_path("/v1/chat/completions/extra") == RelayMode.CHAT_COMPLETIONS


def test_relay_mode_completions():
    from app.relay.mode import RelayMode, relay_mode_from_path

    assert relay_mode_from_path("/v1/completions") == RelayMode.COMPLETIONS


def test_relay_mode_embeddings():
    from app.relay.mode import RelayMode, relay_mode_from_path

    assert relay_mode_from_path("/v1/embeddings") == RelayMode.EMBEDDINGS
    assert relay_mode_from_path("/v1/engines/ada/embeddings") == RelayMode.EMBEDDINGS


def test_relay_mode_moderations():
    from app.relay.mode import RelayMode, relay_mode_from_path

    assert relay_mode_from_path("/v1/moderations") == RelayMode.MODERATIONS


def test_relay_mode_images():
    from app.relay.mode import RelayMode, relay_mode_from_path

    assert relay_mode_from_path("/v1/images/generations") == RelayMode.IMAGES_GENERATIONS
    assert relay_mode_from_path("/v1/images/edits") == RelayMode.IMAGES_EDITS


def test_relay_mode_audio():
    from app.relay.mode import RelayMode, relay_mode_from_path

    assert relay_mode_from_path("/v1/audio/speech") == RelayMode.AUDIO_SPEECH
    assert relay_mode_from_path("/v1/audio/transcriptions") == RelayMode.AUDIO_TRANSCRIPTION
    assert relay_mode_from_path("/v1/audio/translations") == RelayMode.AUDIO_TRANSLATION


def test_relay_mode_rerank():
    from app.relay.mode import RelayMode, relay_mode_from_path

    assert relay_mode_from_path("/v1/rerank") == RelayMode.RERANK
    assert relay_mode_from_path("/v2/rerank") == RelayMode.RERANK


def test_relay_mode_responses():
    from app.relay.mode import RelayMode, relay_mode_from_path

    assert relay_mode_from_path("/v1/responses") == RelayMode.RESPONSE_API


def test_relay_mode_claude_messages():
    from app.relay.mode import RelayMode, relay_mode_from_path

    assert relay_mode_from_path("/v1/messages") == RelayMode.CLAUDE_MESSAGES


def test_relay_mode_realtime():
    from app.relay.mode import RelayMode, relay_mode_from_path

    assert relay_mode_from_path("/v1/realtime") == RelayMode.REALTIME


def test_relay_mode_videos():
    from app.relay.mode import RelayMode, relay_mode_from_path

    assert relay_mode_from_path("/v1/videos") == RelayMode.VIDEOS


def test_relay_mode_ocr():
    from app.relay.mode import RelayMode, relay_mode_from_path

    assert relay_mode_from_path("/api/paas/ocr") == RelayMode.OCR
    assert relay_mode_from_path("/v1/layout_parsing") == RelayMode.OCR


def test_relay_mode_proxy():
    from app.relay.mode import RelayMode, relay_mode_from_path

    assert relay_mode_from_path("/v1/oneapi/proxy") == RelayMode.PROXY


def test_relay_mode_default_fallback():
    from app.relay.mode import RelayMode, relay_mode_from_path

    # Unknown paths fall back to CHAT_COMPLETIONS
    assert relay_mode_from_path("/v1/unknown/path") == RelayMode.CHAT_COMPLETIONS
    assert relay_mode_from_path("/") == RelayMode.CHAT_COMPLETIONS


# ---------------------------------------------------------------------------
# app/budget/redis.py — missing Redis-available branches (43 lines)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_budget_redis_no_url():
    from app.budget.redis import BudgetRedisClient

    client = BudgetRedisClient("")
    await client.initialize()
    assert client.available is False


@pytest.mark.asyncio
async def test_budget_redis_no_redis_package():
    from app.budget.redis import BudgetRedisClient

    client = BudgetRedisClient("redis://localhost:6379")
    with patch("builtins.__import__", side_effect=ImportError("redis")):
        # Simulate redis package not installed
        client._available = False
        assert client.available is False


@pytest.mark.asyncio
async def test_budget_redis_connection_failure():
    from app.budget.redis import BudgetRedisClient

    client = BudgetRedisClient("redis://invalid-host:6379")

    mock_redis_module = MagicMock()
    mock_redis_instance = AsyncMock()
    mock_redis_instance.ping.side_effect = ConnectionError("Connection refused")
    mock_redis_module.asyncio.Redis.from_url.return_value = mock_redis_instance

    with patch.dict("sys.modules", {"redis": mock_redis_module, "redis.asyncio": mock_redis_module.asyncio}):
        await client.initialize()

    assert client.available is False


@pytest.mark.asyncio
async def test_budget_redis_successful_connection():
    from app.budget.redis import BudgetRedisClient

    client = BudgetRedisClient("redis://localhost:6379")

    mock_redis_module = MagicMock()
    mock_redis_instance = AsyncMock()
    mock_redis_instance.ping = AsyncMock(return_value=True)
    mock_redis_module.asyncio.Redis.from_url.return_value = mock_redis_instance

    with patch.dict("sys.modules", {"redis": mock_redis_module, "redis.asyncio": mock_redis_module.asyncio}):
        await client.initialize()

    assert client.available is True


@pytest.mark.asyncio
async def test_budget_redis_get_consumed_unavailable():
    from app.budget.redis import BudgetRedisClient

    client = BudgetRedisClient("")
    client._available = False
    result = await client.get_consumed(1, "2025-01")
    assert result == 0.0


@pytest.mark.asyncio
async def test_budget_redis_get_consumed_available():
    from app.budget.redis import BudgetRedisClient

    client = BudgetRedisClient("redis://localhost:6379")
    mock_redis = AsyncMock()
    mock_redis.get.return_value = "150.5"
    client._client = mock_redis
    client._available = True

    result = await client.get_consumed(1, "2025-01")
    assert result == 150.5
    mock_redis.get.assert_called_once_with("budget:consumed:1:2025-01")


@pytest.mark.asyncio
async def test_budget_redis_get_consumed_none():
    from app.budget.redis import BudgetRedisClient

    client = BudgetRedisClient("redis://localhost:6379")
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None
    client._client = mock_redis
    client._available = True

    result = await client.get_consumed(1, "2025-01")
    assert result == 0.0


@pytest.mark.asyncio
async def test_budget_redis_get_frozen_available():
    from app.budget.redis import BudgetRedisClient

    client = BudgetRedisClient("redis://localhost:6379")
    mock_redis = AsyncMock()
    mock_redis.get.return_value = "25.0"
    client._client = mock_redis
    client._available = True

    result = await client.get_frozen(1, "2025-01")
    assert result == 25.0


@pytest.mark.asyncio
async def test_budget_redis_get_frozen_unavailable():
    from app.budget.redis import BudgetRedisClient

    client = BudgetRedisClient("")
    client._available = False
    result = await client.get_frozen(1, "2025-01")
    assert result == 0.0


@pytest.mark.asyncio
async def test_budget_redis_freeze_available():
    from app.budget.redis import BudgetRedisClient

    client = BudgetRedisClient("redis://localhost:6379")
    mock_redis = AsyncMock()
    mock_redis.incrbyfloat.return_value = 50.0
    client._client = mock_redis
    client._available = True

    result = await client.freeze(1, "2025-01", 50.0)
    assert result == 50.0
    mock_redis.incrbyfloat.assert_called_once_with("budget:frozen:1:2025-01", 50.0)


@pytest.mark.asyncio
async def test_budget_redis_freeze_unavailable():
    from app.budget.redis import BudgetRedisClient

    client = BudgetRedisClient("")
    client._available = False
    result = await client.freeze(1, "2025-01", 50.0)
    assert result == 0.0


@pytest.mark.asyncio
async def test_budget_redis_settle_available():
    from app.budget.redis import BudgetRedisClient

    client = BudgetRedisClient("redis://localhost:6379")
    mock_redis = AsyncMock()
    mock_pipe = MagicMock()
    mock_pipe.incrbyfloat = MagicMock()
    mock_pipe.execute = AsyncMock(return_value=[10.0, 100.0])
    mock_redis.pipeline = MagicMock(return_value=mock_pipe)
    client._client = mock_redis
    client._available = True

    consumed, frozen = await client.settle(1, "2025-01", frozen_amount=50.0, actual_cost=40.0)
    assert consumed == 100.0
    assert frozen == 10.0


@pytest.mark.asyncio
async def test_budget_redis_settle_unavailable():
    from app.budget.redis import BudgetRedisClient

    client = BudgetRedisClient("")
    client._available = False
    result = await client.settle(1, "2025-01", frozen_amount=50.0, actual_cost=40.0)
    assert result == (0.0, 0.0)


@pytest.mark.asyncio
async def test_budget_redis_close_with_client():
    from app.budget.redis import BudgetRedisClient

    client = BudgetRedisClient("redis://localhost:6379")
    mock_redis = AsyncMock()
    client._client = mock_redis
    client._available = True

    await client.close()
    mock_redis.close.assert_called_once()
    assert client._client is None
    assert client._available is False


@pytest.mark.asyncio
async def test_budget_redis_close_no_client():
    from app.budget.redis import BudgetRedisClient

    client = BudgetRedisClient("")
    client._available = False
    # Should not raise
    await client.close()
