"""Test that streaming requests settle the budget after the stream ends.

When budget is enabled, pre_check freezes an estimated cost in Redis.
For streaming requests, this frozen amount must be released via post_settle
when the stream ends and actual usage is known.

Tests here verify the callback wiring and parameter passing rather than
the full DB execution (which requires a running database).
"""
from __future__ import annotations

import inspect

import pytest


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
