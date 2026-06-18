"""Tests for channel type resolution and billing.

TDD: Channel distribution should be registry-based, not hardcoded.
Billing calculations must be accurate (no double-count).
"""
import pytest
from app.routers.v1.relay import _get_adaptor, _estimate_cost
from app.relay.adaptor import ModelConfig


class TestGetAdaptor:
    """_get_adaptor() should resolve adaptors by channel type."""

    def test_deepseek_channel_type(self):
        """_get_adaptor(39) should return a DeepSeekAdaptor instance."""
        adaptor = _get_adaptor(39)
        assert adaptor is not None
        assert adaptor.provider_name == "deepseek"

    def test_glm_channel_type(self):
        """_get_adaptor(41) should return a GLMAdaptor instance."""
        adaptor = _get_adaptor(41)
        assert adaptor is not None
        assert adaptor.provider_name == "glm"

    def test_unknown_channel_type(self):
        """_get_adaptor(999) should return None."""
        adaptor = _get_adaptor(999)
        assert adaptor is None

    def test_channeltype_module(self):
        """Channel type constants should be accessible."""
        from app.relay import channeltype
        assert channeltype.DeepSeek == 39
        assert channeltype.GLM == 41


class TestBilling:
    """Billing calculations must be accurate."""

    def test_estimate_cost_no_double_count(self):
        """Completion tokens should not be double-counted through both ratios.

        With input_ratio=2.0, output_ratio=3.0:
          input: 10 chars//4=1→max(10,1)=10 tokens → 10*2.0=20
          completion: min(100,1024)=100 tokens → 100*3.0=300
          total = 20 + 300 = 320
        Bug would give: 20 + 100*3.0*2.0 = 620
        """
        config = ModelConfig(input_ratio=2.0, output_ratio=3.0)
        body = {
            "messages": [{"content": "hello"}],
            "max_tokens": 100,
        }
        cost = _estimate_cost(body, config)
        assert cost == 320, f"Expected 320, got {cost}"


class TestApiKeyResolution:
    """API key resolution should work per channel type."""

    def test_api_key_for_deepseek(self):
        """DeepSeek should use the deepseek_api_key config."""
        from app.routers.v1.relay import _get_channel_api_key
        from app.relay import channeltype
        key = _get_channel_api_key(channeltype.DeepSeek)
        # Should return a non-empty string or configured value
        assert isinstance(key, str)

    def test_api_key_for_unknown_channel(self):
        """Unknown channel types should return empty string."""
        from app.routers.v1.relay import _get_channel_api_key
        key = _get_channel_api_key(999)
        assert key == ""


class TestProviderAdaptors:
    """Each provider adaptor should register and resolve correctly."""

    def test_qwen_adaptor(self):
        """Qwen adaptor should be registered at channel type 50."""
        from app.relay import channeltype
        adaptor = _get_adaptor(channeltype.AliBailian)
        assert adaptor is not None
        assert adaptor.provider_name == "qwen"
        assert "chat_completions" in adaptor.NATIVE_FORMATS

    def test_kimi_adaptor(self):
        """Kimi adaptor should be registered at channel type 25."""
        from app.relay import channeltype
        adaptor = _get_adaptor(channeltype.Moonshot)
        assert adaptor is not None
        assert adaptor.provider_name == "kimi"
        assert "chat_completions" in adaptor.NATIVE_FORMATS

    def test_minimax_adaptor(self):
        """MiniMax adaptor should be registered at channel type 27."""
        from app.relay import channeltype
        adaptor = _get_adaptor(channeltype.Minimax)
        assert adaptor is not None
        assert adaptor.provider_name == "minimax"
        assert "chat_completions" in adaptor.NATIVE_FORMATS

    def test_each_adaptor_has_models(self):
        """Every adaptor should expose at least one model."""
        for ct in [39, 41, 50, 25, 27]:
            adaptor = _get_adaptor(ct)
            assert adaptor is not None
            models = adaptor.get_supported_models()
            assert len(models) > 0, f"Channel type {ct} has no models"


class TestModelResolution:
    """Model names should resolve to the correct channel type."""

    def test_deepseek_model(self):
        """deepseek-v4-pro should resolve to DeepSeek channel type."""
        from app.relay.registry import registry
        ct = registry.resolve_channel_type("deepseek-v4-pro")
        assert ct == 39

    def test_glm_model(self):
        """glm-5.2 should resolve to GLM channel type."""
        from app.relay.registry import registry
        ct = registry.resolve_channel_type("glm-5.2")
        assert ct == 41

    def test_minimax_model(self):
        """MiniMax-M2.7 should resolve to MiniMax channel type."""
        from app.relay.registry import registry
        ct = registry.resolve_channel_type("MiniMax-M2.7")
        assert ct == 27

    def test_unknown_model(self):
        """Unknown model should return None."""
        from app.relay.registry import registry
        ct = registry.resolve_channel_type("nonexistent-model-v99")
        assert ct is None
