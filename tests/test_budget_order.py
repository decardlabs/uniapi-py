"""Test that balance check runs BEFORE budget pre_check to avoid freeze leaks.

When budget is enabled, pre_check freezes estimated cost in Redis.
If the balance check then fails, the frozen amount is never released.
The fix: check balance first, then pre_check.
"""
from __future__ import annotations

import pytest


class TestBudgetOrdering:
    """Balance check must happen before budget pre_check."""

    def test_balance_check_before_pre_check(self):
        """Verify the relay.py code checks user.balance BEFORE calling
        budget_arbiter.pre_check()."""
        import inspect

        from app.routers.v1 import relay

        source = inspect.getsource(relay._handle_relay)

        # Find the pre_check call position
        pre_check_pos = source.find("budget_arbiter.pre_check(")
        # Find the balance check position (the "Insufficient user balance" raise)
        balance_check_pos = source.find("Insufficient user balance")

        assert pre_check_pos > 0, "pre_check call must exist"
        assert balance_check_pos > 0, "Balance check must exist"

        # The balance check must appear BEFORE the pre_check call
        assert balance_check_pos < pre_check_pos, (
            "Balance check must happen BEFORE budget pre_check. "
            "Currently pre_check at position {} runs before "
            "balance check at position {}.".format(pre_check_pos, balance_check_pos)
        )
