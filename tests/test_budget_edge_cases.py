"""Tests for billing edge cases: zero cost, cache optimization, minimum charges, overdraft."""


class TestBillingEdgeCases:
    """Billing edge cases and boundary conditions."""

    def test_cache_hit_reduces_cost(self):
        """Same input/output: with cache hit should cost less than without."""
        from app.budget.pricing import calculate_cost

        cost_no_cache = calculate_cost("deepseek-v4-pro", 1000, 500, 0)
        cost_with_cache = calculate_cost("deepseek-v4-pro", 1000, 500, 800)
        assert cost_with_cache < cost_no_cache, \
            f"Cache should reduce cost: {cost_with_cache} >= {cost_no_cache}"

    def test_cache_hit_of_all_input(self):
        """When all input tokens are cache hits, only cache price applies."""
        from app.budget.pricing import calculate_cost

        cost = calculate_cost("deepseek-v4-flash", 1000, 500, 1000)
        # input_miss = 0, cache = 1000, output = 500
        # (0/1M)*1 + (1000/1M)*0.02 + (500/1M)*2 = 0.00002 + 0.001 = 0.00102
        expected = round((1000 / 1e6) * 0.02 + (500 / 1e6) * 2, 6)
        assert cost == expected, f"Full cache: expected {expected}, got {cost}"

    def test_minimum_charge_one_micro(self):
        """Cost should be at least 1 micro-yuan, even for tiny usage."""
        from app.budget.pricing import calculate_cost_micro

        cost = calculate_cost_micro("deepseek-v4-pro", 1, 0, 0)
        assert cost >= 1, f"Minimum charge should be 1 micro-yuan, got {cost}"

    def test_micro_yuan_rounds_correctly(self):
        """Conversion from yuan to micro-yuan should round properly."""
        from app.budget.pricing import calculate_cost_micro

        # Very small cost: 1 token of deepseek-v4-pro input = (1/1M)*3 = 0.000003 yuan
        # 0.000003 * 1_000_000 = 3 micro-yuan → max(1, 3) = 3
        cost = calculate_cost_micro("deepseek-v4-pro", 1, 0, 0)
        assert cost == 3, f"Expected 3 micro-yuan, got {cost}"

    def test_estimate_includes_safety_margin(self):
        """Estimate should be >= actual cost (20% safety margin)."""
        from app.budget.pricing import calculate_cost, estimate_cost

        actual = calculate_cost("deepseek-v4-pro", 1000, 500)
        estimated = estimate_cost("deepseek-v4-pro", 1000, 500)
        assert estimated >= actual, \
            f"Estimate {estimated} should be >= actual {actual}"
        # 20% margin: estimated should be ~1.2x actual
        assert estimated <= actual * 1.3, \
            f"Estimate {estimated} should not exceed 1.3x actual {actual}"
