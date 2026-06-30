"""Tests for budget pricing module.

Tests real-currency (yuan) pricing data and cost calculation.
"""
import pytest


class TestPricingData:
    """Pricing data should cover all known models."""

    def test_model_pricing_yuan_has_all_models(self):
        """MODEL_PRICING_YUAN should include models from all adaptors."""
        from app.budget.pricing import MODEL_PRICING_YUAN
        expected = {
            "deepseek-v4-pro", "deepseek-v4-flash",
            "qwen3.7-max", "qwen3.7-plus", "qwen3.6-plus", "qwen3.6-flash",
            "qwen3.5-plus", "qwen3.5-flash",
            "qwen3-coder-plus", "qwen3-coder-flash", "qwen-turbo",
            "glm-5.2", "glm-5.1", "glm-5", "glm-4.7", "glm-4.5-air",
            "glm-4.7-flash", "glm-z1-flash",
            "kimi-k2.7-code", "kimi-k2.7-code-highspeed", "kimi-k2.6", "kimi-k2.5", "kimi-k2",
            "MiniMax-M3", "MiniMax-M2.7", "MiniMax-M2.7-highspeed",
            "MiniMax-M2.5", "MiniMax-M2.5-highspeed",
            "MiniMax-M2.1", "MiniMax-M2.1-highspeed", "MiniMax-M2",
        }
        assert expected.issubset(MODEL_PRICING_YUAN.keys())

    def test_pricing_has_required_keys(self):
        """Each model entry must have input, output, cache_hit."""
        from app.budget.pricing import MODEL_PRICING_YUAN
        for model, prices in MODEL_PRICING_YUAN.items():
            assert "input" in prices, f"{model} missing input"
            assert "output" in prices, f"{model} missing output"
            assert "cache_hit" in prices, f"{model} missing cache_hit"
            assert prices["input"] >= 0
            assert prices["output"] >= 0
            assert prices["cache_hit"] >= 0


class TestCalculateCost:
    """calculate_cost should compute correct yuan amounts."""

    def test_basic_calculation(self):
        """1000 input + 500 output tokens at ¥3/¥6 per million."""
        from app.budget.pricing import calculate_cost
        cost = calculate_cost("deepseek-v4-pro", input_tokens=1000, output_tokens=500)
        # input: 1000/1M * 3 = 0.003
        # output: 500/1M * 6 = 0.003
        # total ≈ 0.006
        assert cost == pytest.approx(0.006, rel=1e-3)

    def test_with_cache_hit(self):
        """Cache-hit tokens use cache_hit price, not input price."""
        from app.budget.pricing import calculate_cost
        # deepseek-v4-pro: input=3, cache_hit=0.025, output=6
        # 2000 total input, 1000 cache hit, 500 output
        # input_miss: 1000/1M * 3 = 0.003
        # cache_hit: 1000/1M * 0.025 = 0.000025
        # output: 500/1M * 6 = 0.003
        # total ≈ 0.006025
        cost = calculate_cost(
            "deepseek-v4-pro",
            input_tokens=2000,
            output_tokens=500,
            cache_hit_tokens=1000,
        )
        assert cost == pytest.approx(0.006025, rel=1e-3)

    def test_zero_tokens(self):
        """Zero tokens should cost zero."""
        from app.budget.pricing import calculate_cost
        cost = calculate_cost("deepseek-v4-pro", input_tokens=0, output_tokens=0)
        assert cost == 0.0


class TestEstimateCost:
    """estimate_cost should apply safety margin."""

    def test_safety_margin_applied(self):
        """Estimated cost should be 1.2x the base calculation."""
        from app.budget.pricing import estimate_cost
        estimated = estimate_cost("deepseek-v4-pro", input_tokens=1000, output_tokens=500)
        # base = 1000/1M*3 + 500/1M*6 = 0.006
        # with 1.2x = 0.0072
        assert estimated == pytest.approx(0.0072, rel=1e-3)
        assert estimated > 0.006  # must be more than base

    def test_no_output_defaults(self):
        """When output_tokens not provided, default to 1000 for estimate."""
        from app.budget.pricing import estimate_cost
        estimated = estimate_cost("deepseek-v4-pro", input_tokens=1000)
        # base = 1000/1M*3 + 1000/1M*6 = 0.009
        # with 1.2x = 0.0108
        assert estimated == pytest.approx(0.0108, rel=1e-3)


class TestComputePeriod:
    """Period string should be YYYY-MM format."""

    def test_period_format(self):
        """Period should match YYYY-MM pattern."""
        from app.budget.pricing import compute_period
        period = compute_period()
        assert len(period) == 7
        assert period[4] == "-"
        parts = period.split("-")
        assert len(parts) == 2
        assert len(parts[0]) == 4  # year
        assert 1 <= int(parts[1]) <= 12  # month


class TestChannelModelConfigsPricing:
    """Channel-level model_configs should override global pricing."""

    def test_get_model_pricing_with_channel_overrides(self):
        """Channel model_configs should take precedence over global pricing."""
        from app.budget.pricing import get_model_pricing

        channel_configs = {
            "deepseek-v4-flash": {
                "input_price": 5.0,
                "output_price": 10.0,
                "cache_hit_price": 0.5,
            }
        }
        result = get_model_pricing("deepseek-v4-flash", channel_model_configs=channel_configs)
        assert result["input"] == 5.0
        assert result["output"] == 10.0
        assert result["cache_hit"] == 0.5

    def test_get_model_pricing_falls_back_to_global(self):
        """If model not in channel_model_configs, fall back to global MODEL_PRICING_YUAN."""
        from app.budget.pricing import get_model_pricing

        channel_configs = {
            "some-other-model": {"input_price": 1.0, "output_price": 2.0, "cache_hit_price": 0.1}
        }
        result = get_model_pricing("deepseek-v4-flash", channel_model_configs=channel_configs)
        assert result["input"] == 1.0  # from MODEL_PRICING_YUAN
        assert result["output"] == 2.0

    def test_get_model_pricing_uses_channel_even_for_unknown_model(self):
        """Channel override should work even if model is not in global pricing at all."""
        from app.budget.pricing import get_model_pricing

        channel_configs = {
            "brand-new-model": {
                "input_price": 8.0,
                "output_price": 16.0,
                "cache_hit_price": 1.0,
            }
        }
        result = get_model_pricing("brand-new-model", channel_model_configs=channel_configs)
        assert result["input"] == 8.0
        assert result["output"] == 16.0
        assert result["cache_hit"] == 1.0

    def test_calculate_cost_with_channel_overrides(self):
        """calculate_cost should use channel overrides when provided."""
        from app.budget.pricing import calculate_cost

        channel_configs = {
            "custom-model": {
                "input_price": 10.0,
                "output_price": 20.0,
                "cache_hit_price": 1.0,
            }
        }
        cost = calculate_cost(
            "custom-model",
            input_tokens=1000,
            output_tokens=500,
            channel_model_configs=channel_configs,
        )
        # input: 1000/1M * 10 = 0.01
        # output: 500/1M * 20 = 0.01
        # total = 0.02
        assert cost == pytest.approx(0.02, rel=1e-3)

    def test_calculate_cost_with_cache_hit_and_overrides(self):
        """Cache-hit should use override cache_hit_price."""
        from app.budget.pricing import calculate_cost

        channel_configs = {
            "custom-model": {
                "input_price": 10.0,
                "output_price": 20.0,
                "cache_hit_price": 2.0,
            }
        }
        cost = calculate_cost(
            "custom-model",
            input_tokens=2000,
            output_tokens=500,
            cache_hit_tokens=1000,
            channel_model_configs=channel_configs,
        )
        # input_miss: 1000/1M * 10 = 0.01
        # cache_hit: 1000/1M * 2 = 0.002
        # output: 500/1M * 20 = 0.01
        # total ≈ 0.022
        assert cost == pytest.approx(0.022, rel=1e-3)

    def test_estimate_cost_with_channel_overrides(self):
        """estimate_cost should use channel overrides."""
        from app.budget.pricing import estimate_cost

        channel_configs = {
            "custom-model": {
                "input_price": 10.0,
                "output_price": 20.0,
                "cache_hit_price": 2.0,
            }
        }
        estimated = estimate_cost(
            "custom-model",
            input_tokens=1000,
            output_tokens=500,
            channel_model_configs=channel_configs,
        )
        # base = 1000/1M*10 + 500/1M*20 = 0.02
        # with 1.2x = 0.024
        assert estimated == pytest.approx(0.024, rel=1e-3)

    def test_calculate_cost_micro_with_channel_overrides(self):
        """calculate_cost_micro should use channel overrides."""
        from app.budget.pricing import calculate_cost_micro

        channel_configs = {
            "custom-model": {
                "input_price": 10.0,
                "output_price": 20.0,
                "cache_hit_price": 1.0,
            }
        }
        micro = calculate_cost_micro(
            "custom-model",
            input_tokens=1000,
            output_tokens=500,
            channel_model_configs=channel_configs,
        )
        # yuan = 0.02, micro = 20000
        assert micro == 20000

    def test_estimate_cost_micro_with_channel_overrides(self):
        """estimate_cost_micro should use channel overrides."""
        from app.budget.pricing import estimate_cost_micro

        channel_configs = {
            "custom-model": {
                "input_price": 10.0,
                "output_price": 20.0,
                "cache_hit_price": 1.0,
            }
        }
        micro = estimate_cost_micro(
            "custom-model",
            input_tokens=1000,
            output_tokens=500,
            channel_model_configs=channel_configs,
        )
        # yuan = 0.024, micro = 24000
        assert micro == 24000

    def test_old_field_names_ratio_completion_ratio(self):
        """Legacy field names (ratio/completion_ratio) should still work."""
        from app.budget.pricing import get_model_pricing

        channel_configs = {
            "deepseek-v4-flash": {
                "ratio": 5.0,
                "completion_ratio": 10.0,
                "cached_input_price": 0.5,
            }
        }
        result = get_model_pricing("deepseek-v4-flash", channel_model_configs=channel_configs)
        assert result["input"] == 5.0
        assert result["output"] == 10.0
        assert result["cache_hit"] == 0.5

    def test_old_field_names_mixed_with_new(self):
        """When both old and new field names are present, new names win."""
        from app.budget.pricing import get_model_pricing

        channel_configs = {
            "deepseek-v4-flash": {
                "ratio": 1.0,
                "completion_ratio": 2.0,
                "input_price": 5.0,
                "output_price": 10.0,
                "cache_hit_price": 0.5,
            }
        }
        result = get_model_pricing("deepseek-v4-flash", channel_model_configs=channel_configs)
        assert result["input"] == 5.0  # input_price wins over ratio
        assert result["output"] == 10.0  # output_price wins over completion_ratio
        assert result["cache_hit"] == 0.5  # cache_hit_price wins

    def test_no_override_falls_back_to_global_calculate(self):
        """Without channel_model_configs, calculate_cost behaves as before."""
        from app.budget.pricing import calculate_cost

        cost = calculate_cost("deepseek-v4-pro", input_tokens=1000, output_tokens=500)
        assert cost == pytest.approx(0.006, rel=1e-3)

    def test_no_override_falls_back_to_global_estimate(self):
        """Without channel_model_configs, estimate_cost behaves as before."""
        from app.budget.pricing import estimate_cost

        estimated = estimate_cost("deepseek-v4-pro", input_tokens=1000, output_tokens=500)
        assert estimated == pytest.approx(0.0072, rel=1e-3)


class TestAllProviderPricing:
    """Verify billing formula correctness for all 5 providers."""

    def test_deepseek_v4_pro_cost(self):
        """deepseek-v4-pro: 1000in+500out, 100 cache_hit."""
        from app.budget.pricing import calculate_cost

        cost = calculate_cost("deepseek-v4-pro", 1000, 500, 100)
        # input_miss=900, cache=100, output=500
        # (900/1M)*3 + (100/1M)*0.025 + (500/1M)*6
        expected = round((900 / 1e6) * 3 + (100 / 1e6) * 0.025 + (500 / 1e6) * 6, 6)
        assert cost == expected, f"deepseek-v4-pro: expected {expected}, got {cost}"

    def test_glm_5_cost(self):
        """GLM-5: 2000in+1000out (no cache)."""
        from app.budget.pricing import calculate_cost

        cost = calculate_cost("glm-5", 2000, 1000)
        expected = round((2000 / 1e6) * 7.2 + (1000 / 1e6) * 23.0, 6)
        assert cost == expected, f"glm-5: expected {expected}, got {cost}"

    def test_qwen37_plus_cost(self):
        """Qwen3.7-plus: 1500in+800out."""
        from app.budget.pricing import calculate_cost

        cost = calculate_cost("qwen3.7-plus", 1500, 800)
        expected = round((1500 / 1e6) * 2.0 + (800 / 1e6) * 8.0, 6)
        assert cost == expected, f"qwen3.7-plus: expected {expected}, got {cost}"

    def test_minimax_m3_cost(self):
        """MiniMax-M3: 500in+300out."""
        from app.budget.pricing import calculate_cost

        cost = calculate_cost("MiniMax-M3", 500, 300)
        expected = round((500 / 1e6) * 2.16 + (300 / 1e6) * 8.64, 6)
        assert cost == expected, f"MiniMax-M3: expected {expected}, got {cost}"

    def test_kimi_k2_cost(self):
        """Kimi-k2: 800in+400out, 200 cache_hit."""
        from app.budget.pricing import calculate_cost

        cost = calculate_cost("kimi-k2", 800, 400, 200)
        # input_miss=600, cache=200, output=400
        expected = round((600 / 1e6) * 2.0 + (200 / 1e6) * 0.4 + (400 / 1e6) * 10.0, 6)
        assert cost == expected, f"kimi-k2: expected {expected}, got {cost}"
