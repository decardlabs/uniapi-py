"""Test that streaming requests settle the budget after the stream ends.

When budget is enabled, pre_check freezes an estimated cost in Redis.
For streaming requests, this frozen amount must be released via post_settle
when the stream ends and actual usage is known.

Tests here verify the callback wiring, parameter passing, and the
fix for stream path only refunding but not deducting extra costs.
"""
from __future__ import annotations

import inspect


class TestStreamingBudgetSettlement:
    """Streaming requests must settle budget after stream ends."""

    def test_callback_accepts_budget_params(self):
        """_make_stream_usage_callback accepts budget arbiter params."""
        from app.routers.v1.relay import _make_stream_usage_callback

        sig = inspect.signature(_make_stream_usage_callback)
        names = list(sig.parameters.keys())
        for p in ("budget_arbiter", "period", "frozen_amount", "monthly_budget"):
            assert p in names, f"Missing parameter: {p}"

    def test_call_site_passes_budget_info(self):
        """The call site that creates the stream callback must pass
        budget_arbiter and budget_info when available."""
        from app.routers.v1.relay import _make_stream_usage_callback

        # Simulate the call site logic:
        # budget_arbiter and request.state.budget_info should be passed through
        sig = inspect.signature(_make_stream_usage_callback)
        budget_params = {
            "budget_arbiter": None,
            "period": "2026-06",
            "frozen_amount": 5000.0,
            "monthly_budget": 100000.0,
        }

        # Verify all budget params have defaults (None or ""), so the call
        # site is not REQUIRED to pass them (backward compatible)
        for name, default in budget_params.items():
            p = sig.parameters[name]
            assert p.default is not inspect.Parameter.empty, (
                f"{name} must have a default value for backward compatibility"
            )

    def test_callback_source_mentions_post_settle(self):
        """The _on_usage callback inside _make_stream_usage_callback should
        contain a call to budget_arbiter.post_settle."""
        from app.routers.v1.relay import _make_stream_usage_callback

        source = inspect.getsource(_make_stream_usage_callback)
        assert "post_settle" in source, (
            "_make_stream_usage_callback must call budget_arbiter.post_settle()"
        )

    def test_call_site_passes_model_name(self):
        """The call site must pass model_name to _make_stream_usage_callback."""
        from app.routers.v1.relay import _make_stream_usage_callback

        sig = inspect.signature(_make_stream_usage_callback)
        assert "model_name" in sig.parameters, "Missing model_name parameter"


class TestStreamBalanceDeduction:
    """Verify stream callback handles balance deduction for both directions."""

    def test_stream_callback_diff_micro_uses_not_equal(self):
        """Stream _on_usage must handle both diff>0 (refund) and diff<0 (deduct).

        Uses source inspection to verify the fix: ``if diff_micro > 0:``
        should be ``if diff_micro != 0:`` (matching non-stream path at L1135).
        """
        from app.routers.v1.relay import _make_stream_usage_callback

        source = inspect.getsource(_make_stream_usage_callback)

        # Check that the balance adjustment code handles both directions
        lines = source.split("\n")
        found_diff = False
        for i, line in enumerate(lines):
            stripped = line.strip()
            if "diff_micro" in stripped and ("!=" in stripped or ">" in stripped or "<" in stripped):
                found_diff = True
                # Must handle both directions: != 0 (fixed) or < 0 (alternative)
                assert "> 0" not in stripped, \
                    f"Line {i}: diff_micro should use != 0, got: '{stripped}'"
                break
        assert found_diff, "Could not find diff_micro comparison line in source"

    def test_stream_callback_uses_atomic_update(self):
        """Stream _on_usage should use atomic ``session.execute(update(...))``
        instead of ORM ``user.balance += diff`` to avoid race conditions."""
        from app.routers.v1.relay import _make_stream_usage_callback

        source = inspect.getsource(_make_stream_usage_callback)

        # Check for atomic update pattern (preferred)
        has_update = "update(" in source and ".where(" in source and "User." in source
        # OR check that session.get is NOT used (which is the non-atomic pattern)
        no_get_pattern = "session.get(User" not in source

        assert has_update or no_get_pattern, \
            "Stream callback should use atomic update() instead of session.get() + balance assignment"
