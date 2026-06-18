"""Tests for BudgetRedisClient."""
import pytest


class TestFakeRedisClient:
    """FakeRedisClient (in-memory) should implement the same interface."""

    @pytest.fixture(autouse=True)
    def setup(self):
        from tests.conftest import FakeRedisClient
        self.redis = FakeRedisClient()

    def test_initialize(self):
        """Initialize should succeed."""
        import asyncio
        asyncio.run(self.redis.initialize())

    def test_available_by_default(self):
        """Client should report as available after init."""
        assert self.redis.available

    def test_get_consumed_defaults_to_zero(self):
        """get_consumed for unknown key returns 0.0."""
        import asyncio
        val = asyncio.run(self.redis.get_consumed(1, "2026-06"))
        assert val == 0.0

    def test_freeze_increases_frozen(self):
        """Freeze should atomically increase frozen balance."""
        import asyncio
        result = asyncio.run(self.redis.freeze(1, "2026-06", 10.0))
        assert result == 10.0
        frozen = asyncio.run(self.redis.get_frozen(1, "2026-06"))
        assert frozen == 10.0

    def test_settle_atomic(self):
        """Settle should unfreeze + deduct in one atomic operation."""
        import asyncio
        # Freeze 10.0 first
        asyncio.run(self.redis.freeze(1, "2026-06", 10.0))
        # Settle: unfreeze 10.0, deduct 6.0 actual
        consumed, frozen = asyncio.run(self.redis.settle(1, "2026-06", 10.0, 6.0))
        assert consumed == 6.0
        assert frozen == 0.0

    def test_multiple_operations_independent(self):
        """Operations for different users/periods should not interfere."""
        import asyncio
        asyncio.run(self.redis.freeze(1, "2026-06", 10.0))
        asyncio.run(self.redis.freeze(2, "2026-06", 20.0))
        asyncio.run(self.redis.freeze(1, "2026-07", 30.0))

        assert asyncio.run(self.redis.get_frozen(1, "2026-06")) == 10.0
        assert asyncio.run(self.redis.get_frozen(2, "2026-06")) == 20.0
        assert asyncio.run(self.redis.get_frozen(1, "2026-07")) == 30.0


class TestBudgetRedisClientSignature:
    """BudgetRedisClient should exist and accept a URL."""

    def test_importable(self):
        """BudgetRedisClient should be importable."""
        from app.budget.redis import BudgetRedisClient
        client = BudgetRedisClient("redis://localhost:6379/0")
        assert client is not None
        assert not client.available  # not initialized yet

    def test_init_no_url(self):
        """With empty URL, client should be unavailable."""
        from app.budget.redis import BudgetRedisClient
        client = BudgetRedisClient("")
        assert not client.available
