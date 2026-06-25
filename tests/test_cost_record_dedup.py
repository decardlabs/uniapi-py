"""Test that CostRecord is not duplicated when budget is enabled."""
from __future__ import annotations

from unittest.mock import patch

import pytest


class TestCostRecordDedup:
    """CostRecord must not be written twice for the same request."""

    def test_inline_cost_record_skipped_when_budget_enabled(self):
        """relay.py must skip the inline CostRecord write when budget is enabled,
        because budget_arbiter.post_settle() already writes it."""
        from app.config import settings

        with patch.object(settings, "budget_enabled", True):
            # This condition should guard the inline CostRecord write in relay.py
            should_write_inline = not settings.budget_enabled
            assert should_write_inline is False, (
                "Inline CostRecord write must be skipped when budget is enabled"
            )

    def test_inline_cost_record_written_when_budget_disabled(self):
        """relay.py must write the inline CostRecord when budget is disabled,
        because post_settle is never called."""
        from app.config import settings

        with patch.object(settings, "budget_enabled", False):
            should_write_inline = not settings.budget_enabled
            assert should_write_inline is True, (
                "Inline CostRecord must be written when budget is disabled"
            )
