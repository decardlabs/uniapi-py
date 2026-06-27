"""Tests for channel type resolution and billing.

TDD: Channel distribution should be registry-based, not hardcoded.
Billing calculations must be accurate (no double-count).
"""
from app.budget.pricing import estimate_cost_micro
from app.routers.v1.relay import _get_adaptor


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

    def test_estimate_cost_micro_deepseek(self):
        """Micro-yuan cost for DeepSeek V4 Flash should be correct.

        input=¥1.0/1M, output=¥2.0/1M
        1000 input + 500 output:
          cost = (1000/1M)*1.0 + (500/1M)*2.0 = 0.002 yuan
          micro = 2000
        """
        cost = estimate_cost_micro("deepseek-v4-flash", 1000, 500)
        # Expected: 1000*1.0/1M + 500*2.0/1M = 0.002¥ → 2000 micro (× 1.2 safety)
        expected = int(round(((1000/1_000_000)*1.0 + (500/1_000_000)*2.0) * 1.2 * 1_000_000))
        assert abs(cost - expected) <= 1, f"Expected ≈{expected}, got {cost}"


class TestApiKeyResolution:
    """API key resolution should work per channel type."""

    def test_api_key_for_deepseek(self):
        """DeepSeek should use the deepseek_api_key config."""
        from app.relay import channeltype
        from app.routers.v1.relay import _get_channel_api_key
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
