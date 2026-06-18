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
            "qwen3.7-max", "qwen3.7-plus", "qwen3-coder-plus", "qwen3-coder-flash",
            "glm-5.2", "glm-5.1", "glm-5", "glm-4-flash", "glm-4",
            "kimi-k2.6", "kimi-k2.5",
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
