"""
Fusion channel-relay adapter tests.

Tests that fusion model calls route through the channel system
instead of using direct provider API keys.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.fusion.adapters.channel_relay import ChannelRelayAdapter
from app.fusion.adapters.registry import AdapterRegistry
from app.fusion.core.engine import FusionConfig, FusionEngine
from app.fusion.schemas import (
    ChatRequest,
    ModelRequest,
    ModelResponse,
    UsageInfo,
)
from app.models.channel import Channel


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_fake_channel(
    channel_id: int = 1,
    key: str = "sk-test-key",
    base_url: str = "",
    model: str = "deepseek-v4-pro",
) -> Channel:
    ch = MagicMock(spec=Channel)
    ch.id = channel_id
    ch.key = key
    ch.base_url = base_url
    ch.type = 39
    ch.weight = 1
    ch.models = model
    ch.priority = 0
    ch.status = 1
    return ch


def _make_fake_adaptor() -> MagicMock:
    """Create a mock relay adaptor (like DeepSeekAdaptor)."""
    adaptor = MagicMock()
    adaptor.provider_name = "deepseek"
    adaptor.DEFAULT_BASE_URL = "https://api.deepseek.com"
    adaptor.get_request_url.return_value = "https://api.deepseek.com/v1/chat/completions"
    # setup_request_headers returns proper Bearer header for the *passed* key
    def _headers(api_key: str):
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
    adaptor.setup_request_headers.side_effect = _headers
    return adaptor


def _make_fake_channel_picker(
    channel: Channel = None,
    model: str = "deepseek-v4-pro",
) -> AsyncMock:
    """Create a mock channel picker that returns (channel, model)."""
    if channel is None:
        channel = _make_fake_channel()
    picker = AsyncMock(return_value=(channel, model))
    return picker


# ===================================================================
# ChannelRelayAdapter
# ===================================================================

class TestChannelRelayAdapter:
    """Unit tests for ChannelRelayAdapter.chat()."""

    @pytest.mark.asyncio
    async def test_chat_returns_model_response(self):
        """Happy path: adapter returns a properly structured ModelResponse."""
        adaptor = _make_fake_adaptor()
        picker = _make_fake_channel_picker()

        adapter = ChannelRelayAdapter(
            provider_name="deepseek",
            channel_picker=picker,
            adaptor=adaptor,
        )

        request = ModelRequest(
            model="deepseek-v4-pro",
            messages=[{"role": "user", "content": "Hello"}],
            temperature=0.7,
            max_tokens=1024,
        )

        # Mock httpx post to return a fake upstream response
        fake_upstream = {
            "id": "chatcmpl-123",
            "object": "chat.completion",
            "model": "deepseek-v4-pro",
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": "Hello! How can I help?"},
                "finish_reason": "stop",
            }],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            },
        }

        with patch("app.fusion.adapters.channel_relay.httpx.AsyncClient") as mock_client:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = fake_upstream
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)

            response = await adapter.chat(request)

        # Verify the channel picker was called
        picker.assert_awaited_once()

        # Verify the response structure
        assert isinstance(response, ModelResponse)
        assert response.model == "deepseek-v4-pro"
        assert response.content == "Hello! How can I help?"
        assert response.finish_reason == "stop"
        assert response.usage.prompt_tokens == 10
        assert response.usage.completion_tokens == 5
        assert response.usage.total_tokens == 15

    @pytest.mark.asyncio
    async def test_chat_passes_correct_body_to_upstream(self):
        """Verify the HTTP request body is correctly built from ModelRequest."""
        adaptor = _make_fake_adaptor()
        channel = _make_fake_channel(key="sk-custom-key")
        picker = _make_fake_channel_picker(channel=channel, model="deepseek-v4-flash")

        adapter = ChannelRelayAdapter(
            provider_name="deepseek",
            channel_picker=picker,
            adaptor=adaptor,
        )

        request = ModelRequest(
            model="deepseek-v4-pro",  # original model
            messages=[{"role": "user", "content": "Hi"}],
            temperature=0.3,
            max_tokens=2048,
            tools=[{"type": "function", "function": {"name": "test"}}],
        )

        with patch("app.fusion.adapters.channel_relay.httpx.AsyncClient") as mock_client:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "id": "x", "object": "chat.completion",
                "model": "deepseek-v4-flash",
                "choices": [{"index": 0, "message": {"role": "assistant", "content": "OK"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            }
            mock_post = AsyncMock(return_value=mock_resp)
            mock_client.return_value.__aenter__.return_value.post = mock_post

            await adapter.chat(request)

        # Verify the HTTP POST call
        mock_post.assert_awaited_once()
        call_args = mock_post.call_args
        assert call_args is not None

        url_arg = call_args[0][0]
        body_arg = call_args[1]["json"]
        headers_arg = call_args[1]["headers"]

        # URL from adaptor.get_request_url
        assert url_arg == "https://api.deepseek.com/v1/chat/completions"

        # Body: model is overridden to upstream model, rest from request
        assert body_arg["model"] == "deepseek-v4-flash"
        assert body_arg["messages"] == [{"role": "user", "content": "Hi"}]
        assert body_arg["temperature"] == 0.3
        assert body_arg["max_tokens"] == 2048
        assert body_arg["stream"] is False
        assert "tools" in body_arg

        # Headers from adaptor.setup_request_headers
        assert headers_arg["Authorization"] == "Bearer sk-custom-key"

    @pytest.mark.asyncio
    async def test_chat_uses_channel_key_and_base_url(self):
        """Channel's key and base_url are used for the upstream call."""
        adaptor = _make_fake_adaptor()
        channel = _make_fake_channel(
            key="sk-channel-specific-key",
            base_url="https://custom-proxy.example.com",
        )
        adaptor.get_request_url.return_value = "https://custom-proxy.example.com/v1/chat/completions"
        picker = _make_fake_channel_picker(channel=channel, model="deepseek-v4-pro")

        adapter = ChannelRelayAdapter("deepseek", picker, adaptor)

        request = ModelRequest(
            model="deepseek-v4-pro",
            messages=[{"role": "user", "content": "test"}],
        )

        with patch("app.fusion.adapters.channel_relay.httpx.AsyncClient") as mock_client:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "id": "x", "object": "chat.completion",
                "model": "deepseek-v4-pro",
                "choices": [{"index": 0, "message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            }
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)

            await adapter.chat(request)

        # Verify adaptor was asked for correct URL/headers
        adaptor.get_request_url.assert_called()
        adaptor.setup_request_headers.assert_called_with("sk-channel-specific-key")

    @pytest.mark.asyncio
    async def test_chat_raises_on_http_error(self):
        """HTTP errors (4xx/5xx) propagate as exceptions."""
        adaptor = _make_fake_adaptor()
        picker = _make_fake_channel_picker()

        adapter = ChannelRelayAdapter("deepseek", picker, adaptor)

        request = ModelRequest(
            model="deepseek-v4-pro",
            messages=[{"role": "user", "content": "test"}],
        )

        with patch("app.fusion.adapters.channel_relay.httpx.AsyncClient") as mock_client:
            mock_resp = MagicMock()
            mock_resp.status_code = 401
            mock_resp.raise_for_status.side_effect = Exception("HTTP 401: Unauthorized")
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)

            with pytest.raises(Exception):
                await adapter.chat(request)

    @pytest.mark.asyncio
    async def test_stream_chat_raises_not_implemented(self):
        """stream_chat is not supported (fusion uses non-streaming only)."""
        adapter = ChannelRelayAdapter("deepseek", AsyncMock(), MagicMock())
        with pytest.raises(NotImplementedError):
            await adapter.stream_chat(ModelRequest())


# ===================================================================
# Integration: Fusion pipeline through ChannelRelayAdapter
# ===================================================================

class TestFusionEngineWithChannelRelay:
    """FusionEngine using ChannelRelayAdapter instead of direct adapters."""

    @pytest.mark.asyncio
    async def test_full_pipeline_through_channel_relay(self):
        """Full fusion pipeline works with ChannelRelayAdapter."""
        registry = AdapterRegistry()

        # Create ChannelRelayAdapters for 2 models
        for model_name, content in [
            ("deepseek-v4-pro", "Answer from pro model."),
            ("deepseek-v4-flash", "Answer from flash model."),
        ]:
            adaptor = _make_fake_adaptor()
            channel = _make_fake_channel(model=model_name)
            picker = _make_fake_channel_picker(channel=channel, model=model_name)

            adapter = ChannelRelayAdapter(
                provider_name="deepseek",
                channel_picker=picker,
                adaptor=adaptor,
            )
            # Replace chat with a mock that returns controlled response
            adapter.chat = AsyncMock(return_value=ModelResponse(
                model=model_name,
                content=content,
                usage=UsageInfo(prompt_tokens=100, completion_tokens=50, total_tokens=150),
            ))
            registry.register(model_name, adapter)

        # Register mocked judge and synth (same pattern)
        judge_adaptor = _make_fake_adaptor()
        judge_picker = _make_fake_channel_picker(model="deepseek-v4-pro")
        judge_adapter = ChannelRelayAdapter("deepseek", judge_picker, judge_adaptor)
        judge_adapter.chat = AsyncMock(return_value=ModelResponse(
            model="deepseek-v4-pro",
            content='{"consensus":["x"],"contradictions":[],"coverage_gaps":[],"unique_insights":{},"blind_spots":[],"confidence":0.8,"recommendation":"ok"}',
            usage=UsageInfo(500, 200, 700),
        ))
        registry.register("judge", judge_adapter)

        synth_adapter = ChannelRelayAdapter("deepseek", AsyncMock(), _make_fake_adaptor())
        synth_adapter.chat = AsyncMock(return_value=ModelResponse(
            model="deepseek-v4-pro",
            content="Final fused answer.",
            usage=UsageInfo(800, 400, 1200),
        ))
        registry.register("synth", synth_adapter)

        config = FusionConfig(
            panel=["deepseek-v4-pro", "deepseek-v4-flash"],
            judge="judge",
            synthesizer="synth",
            timeout_seconds=10,
            retry_count=1,
            fallback_model="deepseek-v4-pro",
        )

        engine = FusionEngine(registry, config)
        request = ChatRequest(
            model="fusion",
            messages=[{"role": "user", "content": "What is the meaning of life?"}],
        )

        response = await engine.execute(request)

        assert response.model == "fusion"
        assert len(response.choices) > 0
        assert response.choices[0]["message"]["content"] == "Final fused answer."
        assert response.fusion_meta is not None
        assert response.fusion_meta.fallback_triggered is False
        assert len(response.fusion_meta.panel_models) == 2

    @pytest.mark.asyncio
    async def test_len_panel_lt_2_fallback(self, sample_request):
        """Only 1 panel model -> skip judge, return directly."""
        registry = AdapterRegistry()
        adaptor = _make_fake_adaptor()
        picker = _make_fake_channel_picker(model="deepseek-v4-pro")
        adapter = ChannelRelayAdapter("deepseek", picker, adaptor)
        adapter.chat = AsyncMock(return_value=ModelResponse(
            model="deepseek-v4-pro",
            content="Direct answer.",
            usage=UsageInfo(50, 25, 75),
        ))
        registry.register("deepseek-v4-pro", adapter)

        config = FusionConfig(
            panel=["deepseek-v4-pro"],
            judge="",
            synthesizer="",
            fallback_model="deepseek-v4-pro",
        )
        engine = FusionEngine(registry, config)
        response = await engine.execute(sample_request)
        assert response.fusion_meta.fallback_triggered is False
        assert response.choices[0]["message"]["content"] == "Direct answer."


@pytest.fixture
def sample_request() -> ChatRequest:
    return ChatRequest(
        model="fusion",
        messages=[{"role": "user", "content": "What is the meaning of life?"}],
    )


# ===================================================================
# Panel model derivation from token + channels
# ===================================================================

class TestFusionPanelSelection:
    """Test the logic that derives panel models from token and channels."""

    def _fake_resolve_channel_type(self, model_name: str) -> int | None:
        """Simulate DeepSeek registry for known models."""
        if model_name in ("deepseek-v4-pro", "deepseek-v4-flash"):
            return 39
        return None

    def test_panel_from_token_models(self):
        """Token with allowed models -> panel uses those models."""
        token_models = ["deepseek-v4-pro", "deepseek-v4-flash"]

        panel = []
        for m in token_models:
            ct = self._fake_resolve_channel_type(m)
            if ct is not None:
                panel.append(m)

        assert panel == ["deepseek-v4-pro", "deepseek-v4-flash"]

    def test_panel_filters_unavailable_models(self):
        """Models not in registry are excluded from panel."""
        token_models = ["deepseek-v4-pro", "nonexistent-model", "deepseek-v4-flash"]

        panel = []
        for m in token_models:
            ct = self._fake_resolve_channel_type(m)
            if ct is not None:
                panel.append(m)

        assert panel == ["deepseek-v4-pro", "deepseek-v4-flash"]
        assert "nonexistent-model" not in panel

    def test_panel_empty_when_no_models_available(self):
        """No models available -> empty panel."""
        token_models = ["some-unknown-model"]

        panel = []
        for m in token_models:
            ct = self._fake_resolve_channel_type(m)
            if ct is not None:
                panel.append(m)

        assert panel == []

    def test_panel_scoring_selects_expensive_for_judge(self):
        """More expensive model is selected as judge/synthesizer."""
        from app.budget.pricing import get_model_pricing

        panel = ["deepseek-v4-pro", "deepseek-v4-flash"]
        scored = []
        for m_name in panel:
            try:
                p = get_model_pricing(m_name)
                scored.append((p["input"] + p["output"], m_name))
            except KeyError:
                continue
        scored.sort(reverse=True)

        assert len(scored) == 2
        best = scored[0][1]
        # v4-pro should be more expensive than v4-flash
        assert best == "deepseek-v4-pro"
